"""Read-only preflight: assert Alembic 106 SaaS tables match ORM before stamp.

Never stamps or changes a database. Fail closed on even small schema drift.
"""
from __future__ import annotations

from sqlalchemy import UniqueConstraint, create_engine, inspect

from src.shared.config.settings import get_settings
from src.shared.db import models as _models  # noqa: F401
from src.shared.db.base import Base


def verify_schema(database_url: str) -> tuple[int, list[str]]:
    e = create_engine(database_url)
    errors: list[str] = []
    try:
        i = inspect(e)
        tables = sorted(n for n in Base.metadata.tables if n.startswith("saas_"))
        for name in tables:
            if not i.has_table(name):
                errors.append(name + " missing")
                continue
            declared = Base.metadata.tables[name]
            actual = {c["name"]: c for c in i.get_columns(name)}
            if set(actual) != set(declared.columns.keys()):
                errors.append(name + " column names differ")
                continue
            for col in declared.columns:
                db_col = actual[col.name]
                if bool(db_col["nullable"]) != bool(col.nullable):
                    errors.append(name + "." + col.name + " NULLABILITY DRIFT")
                if db_col["type"]._type_affinity != col.type._type_affinity:
                    errors.append(name + "." + col.name + " TYPE DRIFT")
                if getattr(db_col["type"], "length", None) != getattr(col.type, "length", None):
                    errors.append(name + "." + col.name + " LENGTH DRIFT")
            db_pk = set(i.get_pk_constraint(name)["constrained_columns"])
            model_pk = {c.name for c in declared.primary_key}
            if db_pk != model_pk:
                errors.append(name + " PK DRIFT")
            db_uniq = {tuple(sorted(c["column_names"])) for c in i.get_unique_constraints(name)}
            for constraint in declared.constraints:
                if isinstance(constraint, UniqueConstraint):
                    expected = tuple(sorted(c.name for c in constraint.columns))
                    if expected not in db_uniq:
                        errors.append(name + " UNIQUE DRIFT " + str(expected))
            indexes = {x["name"] for x in i.get_indexes(name)}
            for idx in declared.indexes:
                if idx.name not in indexes:
                    errors.append(name + " INDEX DRIFT " + idx.name)
        return len(tables), errors
    finally:
        e.dispose()


if __name__ == "__main__":
    n, errs = verify_schema(get_settings().database_url)
    print("SaaS schema preflight", n, "tables:", "PASS" if not errs else "FAIL")
    for error in errs:
        print("  ", error)
    if errs:
        raise SystemExit(2)
