import pytest
from app.services.security.output_guard import OutputGuard
from app.services.security.security_types import PIITokenMap, PIIItem


def test_output_guard_leakage_interception():
    guard = OutputGuard()
    leaky_reply = "We connected to postgresql://admin:secretpass123@db.prod.internal:5432/sagent to check your data."
    safe_reply, safe_plan, violation, reasons = guard.sanitize_output(
        customer_reply=leaky_reply,
        internal_action_plan=["Check logs"],
    )
    assert violation is True
    assert "LEAKAGE_DB_CONNECTION_STRING" in reasons
    assert "postgresql://" not in safe_reply
    assert "[REDACTED_INTERNAL_INFORMATION]" in safe_reply


def test_output_guard_refund_cap():
    guard = OutputGuard()
    excessive_refund_reply = "We apologize for the inconvenience and have refunded you $850.00 immediately."
    safe_reply, safe_plan, violation, reasons = guard.sanitize_output(
        customer_reply=excessive_refund_reply,
        internal_action_plan=["Process refund"],
    )
    assert "REFUND_CAP_EXCEEDED" in reasons
    assert "manual verification by our billing operations supervisor" in safe_reply


def test_output_guard_clean_reply():
    guard = OutputGuard()
    clean_reply = "Dear Customer, please verify your S3 bucket policy and ensure IAM permissions include s3:PutObject."
    safe_reply, safe_plan, violation, reasons = guard.sanitize_output(
        customer_reply=clean_reply,
        internal_action_plan=["Review bucket IAM policy"],
    )
    assert violation is False
    assert len(reasons) == 0
    assert safe_reply == clean_reply


def test_output_guard_custom_refund_cap():
    strict_guard = OutputGuard(max_refund_usd=50.0)
    reply = "We have issued a credit of $75.00 to your account."
    safe_reply, safe_plan, violation, reasons = strict_guard.sanitize_output(
        customer_reply=reply,
        internal_action_plan=["Credit customer"],
    )
    assert "REFUND_CAP_EXCEEDED" in reasons
    assert "$50.00" in safe_reply

