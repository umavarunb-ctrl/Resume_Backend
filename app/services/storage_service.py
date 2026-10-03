"""Resume file storage service integrating Oracle Cloud Infrastructure (OCI) Object Storage."""

import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from fastapi import HTTPException, status

try:
    import oci
    OCI_AVAILABLE = True
except ImportError:
    OCI_AVAILABLE = False

from app.core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service for managing files in OCI Object Storage."""

    def __init__(self) -> None:
        self.enabled = False
        self.namespace = settings.OCI_NAMESPACE
        self.bucket_name = settings.OCI_BUCKET_NAME
        
        if (
            settings.OCI_TENANCY_OCID and 
            settings.OCI_USER_OCID and 
            settings.OCI_FINGERPRINT and 
            settings.OCI_REGION and 
            settings.OCI_PRIVATE_KEY_PATH and
            self.namespace and 
            self.bucket_name
        ):
            if not OCI_AVAILABLE:
                logger.warning("OCI configuration provided, but 'oci' python package is not installed.")
                return
            
            try:
                self.oci_config = {
                    "user": settings.OCI_USER_OCID,
                    "key_file": settings.OCI_PRIVATE_KEY_PATH,
                    "fingerprint": settings.OCI_FINGERPRINT,
                    "tenancy": settings.OCI_TENANCY_OCID,
                    "region": settings.OCI_REGION
                }
                oci.config.validate_config(self.oci_config)
                self.client = oci.object_storage.ObjectStorageClient(self.oci_config)
                self.enabled = True
            except Exception as e:
                logger.error(f"Failed to initialize OCI Object Storage client: {e}")
        else:
            logger.info("OCI configuration incomplete. Object Storage is disabled.")

    def generate_object_name(self, original_filename: str, resume_id: str) -> str:
        """Generate a collision-resistant object name based on year/month/id."""
        now = datetime.now(timezone.utc)
        return f"resumes/{now.year}/{now.month:02d}/{resume_id}.pdf"

    def upload_file(self, file_bytes: bytes, object_name: str, content_type: str = "application/pdf") -> None:
        """Upload a file to Oracle Cloud Object Storage."""
        if not self.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Object Storage is not configured."
            )
            
        try:
            self.client.put_object(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                object_name=object_name,
                put_object_body=file_bytes,
                content_type=content_type
            )
            logger.info("Successfully uploaded object to OCI Object Storage.")
        except oci.exceptions.ServiceError as e:
            logger.error(f"OCI Service Error during upload: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to upload file to cloud storage."
            )
        except Exception as e:
            logger.error(f"Unexpected error during OCI upload: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal storage error during upload."
            )

    def delete_file(self, object_name: str) -> None:
        """Delete a file from Oracle Cloud Object Storage."""
        if not self.enabled:
            return
            
        try:
            self.client.delete_object(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                object_name=object_name
            )
            logger.info("Successfully deleted object from OCI Object Storage.")
        except oci.exceptions.ServiceError as e:
            if e.status == 404:
                logger.warning(f"Object not found in OCI during deletion: {object_name}")
            else:
                logger.error(f"OCI Service Error during deletion: {e}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Failed to delete file from cloud storage."
                )
        except Exception as e:
            logger.error(f"Unexpected error during OCI deletion: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal storage error during deletion."
            )

    def generate_presigned_url(self, object_name: str, expires_in_minutes: int = 15) -> str:
        """Generate a short-lived Pre-Authenticated Request (PAR) URL for accessing the resume."""
        if not self.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Object Storage is not configured."
            )
            
        try:
            expires = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)
            par_name = f"access_{uuid.uuid4().hex[:8]}"
            
            par_details = oci.object_storage.models.CreatePreauthenticatedRequestDetails(
                name=par_name,
                access_type="ObjectRead",
                object_name=object_name,
                time_expires=expires
            )
            
            response = self.client.create_preauthenticated_request(
                namespace_name=self.namespace,
                bucket_name=self.bucket_name,
                create_preauthenticated_request_details=par_details
            )
            
            # Construct the full URL
            # The format is https://objectstorage.{region}.oraclecloud.com{access_uri}
            base_url = f"https://objectstorage.{settings.OCI_REGION}.oraclecloud.com"
            access_uri = response.data.access_uri
            
            return f"{base_url}{access_uri}"
            
        except oci.exceptions.ServiceError as e:
            logger.error(f"OCI Service Error generating PAR: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to generate secure access URL."
            )
        except Exception as e:
            logger.error(f"Unexpected error generating PAR: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error generating secure access URL."
            )
