import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from app.services.storage_service import StorageService
from app.core.config import settings

@pytest.fixture
def mock_settings():
    with patch("app.services.storage_service.settings") as mock:
        mock.OCI_TENANCY_OCID = "ocid1.tenancy.oc1..test"
        mock.OCI_USER_OCID = "ocid1.user.oc1..test"
        mock.OCI_FINGERPRINT = "test_fingerprint"
        mock.OCI_REGION = "us-ashburn-1"
        mock.OCI_PRIVATE_KEY_PATH = "test_key.pem"
        mock.OCI_NAMESPACE = "test_namespace"
        mock.OCI_BUCKET_NAME = "test_bucket"
        yield mock

@pytest.fixture
def storage_service(mock_settings):
    with patch("app.services.storage_service.oci") as mock_oci:
        mock_oci.object_storage.ObjectStorageClient.return_value = MagicMock()
        service = StorageService()
        yield service

def test_missing_oci_configuration():
    with patch("app.services.storage_service.settings") as mock_settings:
        mock_settings.OCI_TENANCY_OCID = None
        service = StorageService()
        assert not service.enabled

def test_valid_oci_configuration(storage_service):
    assert storage_service.enabled
    assert storage_service.namespace == "test_namespace"
    assert storage_service.bucket_name == "test_bucket"

def test_upload_success(storage_service):
    storage_service.upload_file(b"test", "resumes/2026/10/test.pdf")
    storage_service.client.put_object.assert_called_once()

def test_upload_failure(storage_service):
    import oci
    storage_service.client.put_object.side_effect = oci.exceptions.ServiceError(
        status=500, code="InternalError", message="Test", headers={}
    )
    with pytest.raises(HTTPException) as exc:
        storage_service.upload_file(b"test", "resumes/2026/10/test.pdf")
    assert exc.value.status_code == 502

def test_delete_success(storage_service):
    storage_service.delete_file("resumes/2026/10/test.pdf")
    storage_service.client.delete_object.assert_called_once()

def test_delete_failure(storage_service):
    import oci
    storage_service.client.delete_object.side_effect = oci.exceptions.ServiceError(
        status=500, code="InternalError", message="Test", headers={}
    )
    with pytest.raises(HTTPException) as exc:
        storage_service.delete_file("resumes/2026/10/test.pdf")
    assert exc.value.status_code == 502

def test_delete_not_found(storage_service):
    import oci
    storage_service.client.delete_object.side_effect = oci.exceptions.ServiceError(
        status=404, code="ObjectNotFound", message="Test", headers={}
    )
    # Should not raise exception
    storage_service.delete_file("resumes/2026/10/test.pdf")

def test_generate_presigned_url(storage_service):
    mock_response = MagicMock()
    mock_response.data.access_uri = "/p/test/access"
    storage_service.client.create_preauthenticated_request.return_value = mock_response
    
    url = storage_service.generate_presigned_url("test.pdf")
    assert "https://objectstorage.us-ashburn-1.oraclecloud.com/p/test/access" == url
