import pytest
from app.services.credential_crypto import CredentialCrypto
from cryptography.fernet import Fernet


@pytest.fixture
def crypto():
    key = Fernet.generate_key().decode()
    return CredentialCrypto(key)


def test_encrypt_decrypt_round_trip(crypto):
    plaintext = "super-secret-password-123!"
    ciphertext = crypto.encrypt(plaintext)
    assert ciphertext != plaintext  # encrypted is different
    assert crypto.decrypt(ciphertext) == plaintext  # round-trip recovers original


def test_encrypted_value_is_not_plaintext(crypto):
    plaintext = "mysecret"
    ciphertext = crypto.encrypt(plaintext)
    assert plaintext not in ciphertext  # not visible in ciphertext


def test_different_encryptions_of_same_value(crypto):
    # Fernet uses random IV so same plaintext → different ciphertext each time
    c1 = crypto.encrypt("same")
    c2 = crypto.encrypt("same")
    assert c1 != c2
    assert crypto.decrypt(c1) == "same"
    assert crypto.decrypt(c2) == "same"
