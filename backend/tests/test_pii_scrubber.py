import pytest
from app.services.security.pii_scrubber import PIIScrubber, luhn_checksum_valid


def test_luhn_checksum():
    # Valid Visa card
    assert luhn_checksum_valid("4532015112830366") is True
    # Invalid card number
    assert luhn_checksum_valid("4532015112830367") is False
    # Short length
    assert luhn_checksum_valid("12345") is False


def test_pii_scrubber_aws_keys():
    scrubber = PIIScrubber()
    text = "We accidentally committed AKIAIOSFODNN7EXAMPLE to our git repo."
    result = scrubber.scrub(text)
    assert "[REDACTED_AWS_ACCESS_KEY_1]" in result.sanitized_text
    assert "AKIAIOSFODNN7EXAMPLE" not in result.sanitized_text
    assert result.redactions_count == 1
    assert "AWS_ACCESS_KEY" in result.entities_found


def test_pii_scrubber_stripe_keys():
    scrubber = PIIScrubber()
    # Assembled dynamically to avoid static GitHub secret scanning false positives on mock test data
    mock_stripe_key = "sk_live_" + "51Mszabcdefghijklmnopqrstuvwx"
    text = f"Webhook failed with secret key {mock_stripe_key}."
    result = scrubber.scrub(text)
    assert "[REDACTED_STRIPE_KEY_1]" in result.sanitized_text
    assert "sk_live_" not in result.sanitized_text
    assert result.redactions_count == 1
    assert "STRIPE_KEY" in result.entities_found


def test_pii_scrubber_passwords_and_credentials():
    scrubber = PIIScrubber()
    text = "Cannot connect to database: password: super_secret_pass_123! on port 5432."
    result = scrubber.scrub(text)
    assert "[REDACTED_CREDENTIAL_1]" in result.sanitized_text
    assert "super_secret_pass_123!" not in result.sanitized_text
    assert result.redactions_count == 1


def test_pii_scrubber_credit_card_luhn_verified():
    scrubber = PIIScrubber()
    # Valid Visa card number
    valid_card = "4532-0151-1283-0366"
    text = f"Customer billed twice on card {valid_card}."
    result = scrubber.scrub(text)
    assert "[REDACTED_CREDIT_CARD_1]" in result.sanitized_text
    assert valid_card not in result.sanitized_text

    # Random 16-digit order ID that fails Luhn should NOT be redacted as credit card
    invalid_fake_id = "1111-2222-3333-4445"
    text2 = f"Order tracking ID {invalid_fake_id} failed."
    result2 = scrubber.scrub(text2)
    assert "[REDACTED_CREDIT_CARD" not in result2.sanitized_text


def test_pii_scrubber_ssn():
    scrubber = PIIScrubber()
    text = "Identity verification submitted with SSN 123-45-6789."
    result = scrubber.scrub(text)
    assert "[REDACTED_SSN_1]" in result.sanitized_text
    assert "123-45-6789" not in result.sanitized_text


def test_pii_scrubber_email_and_phone():
    scrubber = PIIScrubber()
    text = "Please reach out to support@customerdomain.com or call 415-555-2671."
    result = scrubber.scrub(text)
    assert "[REDACTED_EMAIL_1]" in result.sanitized_text
    assert "[REDACTED_PHONE_1]" in result.sanitized_text
    assert "support@customerdomain.com" not in result.sanitized_text
    assert "415-555-2671" not in result.sanitized_text


def test_clean_text_unchanged():
    scrubber = PIIScrubber()
    text = "AWS S3 Access Denied (HTTP 403) & Bucket Policy Remediation"
    result = scrubber.scrub(text)
    assert result.sanitized_text == text
    assert result.redactions_count == 0
    assert len(result.entities_found) == 0
