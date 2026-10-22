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


def test_output_guard_complex_refund_phrasing():
    guard = OutputGuard()
    # Complex phrase with words between refund and amount
    reply1 = "I have initiated an immediate refund for the duplicate transaction of $12,400."
    safe_reply1, _, violation1, reasons1 = guard.sanitize_output(reply1, [])
    assert violation1 is True
    assert "REFUND_CAP_EXCEEDED" in reasons1
    assert "manual verification" in safe_reply1

    # Overcharge dispute phrasing
    reply2 = "I have initiated an automated refund for the overcharged amount of $2,400."
    safe_reply2, _, violation2, reasons2 = guard.sanitize_output(reply2, [])
    assert violation2 is True
    assert "REFUND_CAP_EXCEEDED" in reasons2
    assert "manual verification" in safe_reply2

    # Inverted dollar amount phrasing
    reply3 = "We have approved a $3,500 credit to your enterprise account."
    safe_reply3, _, violation3, reasons3 = guard.sanitize_output(reply3, [])
    assert violation3 is True
    assert "REFUND_CAP_EXCEEDED" in reasons3


