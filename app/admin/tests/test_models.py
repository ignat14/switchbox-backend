def test_models_importable():
    from app.audit.models import AuditLog
    from app.base import Base
    from app.flags.models import Flag
    from app.projects.models import Project
    from app.rules.models import Rule

    assert Base is not None
    assert Project.__tablename__ == "projects"
    assert Flag.__tablename__ == "flags"
    assert Rule.__tablename__ == "rules"
    assert AuditLog.__tablename__ == "audit_logs"


def test_flag_has_unique_constraint():
    from app.flags.models import Flag

    unique_constraints = [
        c
        for c in Flag.__table__.constraints
        if hasattr(c, "columns") and len(c.columns) > 1
    ]
    column_names = {
        frozenset(col.name for col in c.columns) for c in unique_constraints
    }
    assert frozenset({"project_id", "key", "environment"}) in column_names


def test_flag_has_check_constraint():
    from app.flags.models import Flag

    check_constraints = [
        c
        for c in Flag.__table__.constraints
        if c.__class__.__name__ == "CheckConstraint"
    ]
    assert len(check_constraints) == 1
    assert "rollout_pct" in str(check_constraints[0].sqltext)
