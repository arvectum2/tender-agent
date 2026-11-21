import Foundation
import Security
#if os(iOS)
import XCTest
@testable import TenderAgent
#endif

// Test-only trust anchor, no global trust-store changes and no redirects.
final class StageTrust: NSObject, URLSessionDelegate, URLSessionTaskDelegate, @unchecked Sendable {
    let certificate: SecCertificate
    init(_ cert: SecCertificate) {certificate=cert}
    func urlSession(_ session:URLSession,didReceive challenge:URLAuthenticationChallenge,completionHandler:@escaping @Sendable(URLSession.AuthChallengeDisposition,URLCredential?)->Void) {
        guard challenge.protectionSpace.host=="127.0.0.1",challenge.protectionSpace.authenticationMethod==NSURLAuthenticationMethodServerTrust,let trust=challenge.protectionSpace.serverTrust,
              SecTrustSetAnchorCertificates(trust,[certificate] as CFArray)==errSecSuccess,SecTrustSetAnchorCertificatesOnly(trust,true)==errSecSuccess,SecTrustEvaluateWithError(trust,nil) else{completionHandler(.cancelAuthenticationChallenge,nil);return}
        completionHandler(.useCredential,URLCredential(trust:trust))
    }
    func urlSession(_ session:URLSession,task:URLSessionTask,willPerformHTTPRedirection response:HTTPURLResponse,newRequest request:URLRequest,completionHandler:@escaping @Sendable(URLRequest?)->Void){completionHandler(nil)}
}

struct StageFixture:Decodable {
    let origin:String;let token:String;let foreignToken:String;let caseId:String;let normKey:String;let planId:String;let certificateDer:String;let caDer:String;let caBase64:String?
}

struct StageAcceptance {
    static func require(_ condition:Bool,_ stage:String)throws {
        if !condition {throw NSError(domain:"StageAcceptance."+stage,code:1)}
    }
    static func run(_ f:StageFixture,caData:Data) async throws {
        let u=try CompanyAPIClient.validatedOrigin(f.origin)
        try require(u.host=="127.0.0.1" && u.port != nil,"loopback")
        guard let cert=SecCertificateCreateWithData(nil,caData as CFData) else{throw CompanyConnectionError.invalidResponse}
        let config=URLSessionConfiguration.ephemeral;config.urlCache=nil;config.httpShouldSetCookies=false
        let session=URLSession(configuration:config,delegate:StageTrust(cert),delegateQueue:nil)
        defer{session.finishTasksAndInvalidate()}
        let a=try CompanyAPIClient(origin:f.origin,token:f.token,session:session)
        let b=try CompanyAPIClient(origin:f.origin,token:f.foreignToken,session:session)
        let identity=try await a.identity(),other=try await b.identity()
        try require(identity.legalAccepted && identity.role=="owner" && identity.customerId != other.customerId,"identity")
        let portfolio=try await a.portfolio(for:identity),foreign=try await b.portfolio(for:other)
        try require(foreign.items.isEmpty,"foreign portfolio")
        guard let item=portfolio.items.first(where:{$0.id==f.caseId}) else{throw CompanyConnectionError.invalidResponse}
        print("NATIVE identity & portfolio PASS")
        let history=try await a.priceHistory(caseID:item.id,identity:identity)
        try require(history.items.count==2 && history.items[0].revision==2 && history.items[0].itemizedEstimate?.lines.first?.normBinding?.normKey==f.normKey,"browser saved version")
        guard let plan=history.items.first(where:{$0.id==f.planId}) else{throw CompanyConnectionError.invalidResponse}
        let baseline=CompanyActualBaseline(scenario:plan)
        let snapshots=try await a.actualHistory(caseID:item.id,identity:identity,baseline:baseline)
        guard let snapshot=snapshots.first,let row=CompanyActualEvidenceRow.rows(snapshot).first else{throw CompanyConnectionError.invalidResponse}
        try require(snapshot.result.totals.reportedTotalRub=="12000.00","actual amount")
        let target=CompanyActualEvidenceTarget(baseline:baseline,snapshot:snapshot,row:row)
        _=try await a.actualEvidenceBinding(caseID:item.id,identity:identity,target:target)
        let chosen=try CompanyActualSampleSelection.make(identity:identity,item:item,target:target,latestSnapshotID:snapshot.id)
        let sample=try await a.actualSamplePreview(identity:identity,selections:[chosen],comparable:true,distinct:true)
        try require(sample.distinctCaseCount==1 && sample.reportedUnitRateDistributionRub.median=="1000.000","sample")
        let norms=try await a.normPage(identity:identity)
        try require(norms.items.count==1 && norms.items[0].normKey==f.normKey,"norm")
        print("NATIVE estimate, actual, sample & norm PASS")
        let catalog=try await a.historicalCatalog(identity:identity,item:item)
        let selection=CompanyHistoricalSelection(referenceRegistryNumber:CompanyHistoricalCatalog.aksay,selectedRegistryNumbers:[CompanyHistoricalCatalog.aksay,"0119200000126013647"],confirmReviewSourceScope:true)
        let preview=try await a.historicalPreview(identity:identity,item:item,catalog:catalog,selection:selection)
        try require(preview.observations.count==2 && preview.targetReferenceIdentityMatches,"historical preview")
        let registry=try await a.reviewedContracts(identity:identity,item:item)
        try require(registry.releaseRevision==0 && registry.activeGroups.isEmpty,"empty registry")
        do{_=try await b.reviewedContracts(identity:other,item:item);throw NSError(domain:"foreign registry accepted",code:1)}
        catch CompanyConnectionError.http(404){}
        do{_=try await b.priceHistory(caseID:item.id,identity:other);throw NSError(domain:"foreign scenario accepted",code:1)}
        catch CompanyConnectionError.http(404){}
        print("PRICE01_REAL_HTTPS_NATIVE_PASS: history, actual, sample, norm, archive, registry, foreign 404")
    }
}


#if os(macOS)
@main struct StageRunner {
    static func main() async throws {
        let path=ProcessInfo.processInfo.environment["PRICE01_FIXTURE"]!
        let f=try TenderAgentJSON.makeDecoder().decode(StageFixture.self,from:Data(contentsOf:URL(fileURLWithPath:path)))
        try await StageAcceptance.run(f,caData:Data(contentsOf:URL(fileURLWithPath:f.caDer)))
    }
}
#elseif os(iOS)
final class CompanyStageAcceptanceTests:XCTestCase {
    func testRealHTTPSStage() async throws {
        guard let encoded=ProcessInfo.processInfo.environment["PRICE01_STAGE_FIXTURE"],let bytes=Data(base64Encoded:encoded) else{throw XCTSkip("Disposable local HTTPS staging only")}
        let f=try TenderAgentJSON.makeDecoder().decode(StageFixture.self,from:bytes)
        guard let encodedCA=f.caBase64,let ca=Data(base64Encoded:encodedCA) else{throw CompanyConnectionError.invalidResponse}
        try await StageAcceptance.run(f,caData:ca)
    }
}
#endif
