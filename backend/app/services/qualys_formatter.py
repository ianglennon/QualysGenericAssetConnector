"""
Qualys CSAM payload formatter.

Transforms generic asset records into Qualys CSAM connector sync format.
"""
import ipaddress
import uuid
from typing import Any
from datetime import datetime


def classify_ip_type(ip_str: str) -> str:
    """Classify an IP address as LOCAL, PRIVATE, ELASTIC, or PUBLIC.
    
    - LOCAL: 127.0.0.0/8 (loopback)
    - PRIVATE: RFC1918 addresses (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    - ELASTIC: AWS elastic IPs (not implemented - treated as PUBLIC for now)
    - PUBLIC: Everything else
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        
        # Check for loopback
        if ip.is_loopback:
            return "LOCAL"
        
        # Check for private (RFC1918)
        if ip.is_private:
            return "PRIVATE"
        
        # Everything else is public (ELASTIC would require AWS-specific detection)
        return "PUBLIC"
    except ValueError:
        # Invalid IP, default to PUBLIC
        return "PUBLIC"


def format_network_interface(interface_data: dict[str, Any]) -> dict[str, Any]:
    """Format a network interface with IP type classification."""
    result: dict[str, Any] = {}
    
    if "interfaceName" in interface_data:
        result["interfaceName"] = interface_data["interfaceName"]
    
    if "macAddress" in interface_data:
        result["macAddress"] = interface_data["macAddress"]
    
    if "address" in interface_data:
        result["address"] = interface_data["address"]
        # Classify the IP type
        result["type"] = classify_ip_type(interface_data["address"])
    
    if "gatewayAddress" in interface_data:
        result["gatewayAddress"] = interface_data["gatewayAddress"]
    
    if "dnsAddress" in interface_data:
        result["dnsAddress"] = interface_data["dnsAddress"]
    
    if "hostName" in interface_data:
        result["hostName"] = interface_data["hostName"]
    
    if "ipv4Address" in interface_data:
        result["ipv4Address"] = interface_data["ipv4Address"]
    
    if "ipv6Address" in interface_data:
        result["ipv6Address"] = interface_data["ipv6Address"]
    
    if "networkUuid" in interface_data:
        result["networkUuid"] = interface_data["networkUuid"]
    
    return result


def format_asset_for_qualys(record: dict[str, Any]) -> dict[str, Any]:
    """Transform a generic asset record into Qualys CSAM format.
    
    Maps transformed fields (after field mapping) to the Qualys CSAM schema.
    Builds identityAttributes and coreAttributes from the flat record.
    """
    asset: dict[str, Any] = {
        "identityAttributes": {},
        "coreAttributes": {}
    }
    
    # Identity attributes mapping
    identity_mappings = {
        "qualysAssetId": "qualysAssetId",
        "sourceNativeKey": "sourceNativeKey",
        "instanceUuid": "instanceUuid",
        "instanceUuidSource": "instanceUuidSource",
        "hostName": "hostName",
        "netBiosName": "netBiosName",
        "fqdn": "fqdn",
        "macAddress": "macAddress",
        "ipAddress": "ipAddress",
        "serialNumber": "serialNumber",
        "hardwareUuid": "hardwareUuid",
        "networkUuid": "networkUuid"
    }
    
    for qualys_field, source_field in identity_mappings.items():
        if source_field in record:
            asset["identityAttributes"][qualys_field] = record[source_field]
    
    # Core attributes mapping
    core_mappings = {
        "lastLoggedOnUser": "lastLoggedOnUser",
        "operatingSystem": "operatingSystem",
        "hostName": "hostName",
        "address": "address",
        "dnsName": "dnsName",
        "netBiosName": "netBiosName",
        "isContainer": "isContainer",
        "fqdn": "fqdn",
        "domain": "domain",
        "osVersion": "osVersion",
        "osArchitecture": "osArchitecture",
        "domainRole": "domainRole"
    }
    
    for qualys_field, source_field in core_mappings.items():
        if source_field in record:
            asset["coreAttributes"][qualys_field] = record[source_field]
    
    # Handle nested structures if provided
    if "biosInfo" in record:
        asset["coreAttributes"]["biosInfo"] = record["biosInfo"]
    
    if "processor" in record:
        asset["coreAttributes"]["processor"] = record["processor"]
    
    if "ports" in record:
        asset["coreAttributes"]["ports"] = record["ports"]
    
    if "networkInterfaces" in record:
        # Format each interface with IP type classification
        asset["coreAttributes"]["networkInterfaces"] = [
            format_network_interface(iface) for iface in record["networkInterfaces"]
        ]
    
    if "softwares" in record:
        asset["coreAttributes"]["softwares"] = record["softwares"]
    
    if "services" in record:
        asset["coreAttributes"]["services"] = record["services"]
    
    if "volumes" in record:
        asset["coreAttributes"]["volumes"] = record["volumes"]
    
    if "accounts" in record:
        asset["coreAttributes"]["accounts"] = record["accounts"]
    
    if "businessMetaData" in record:
        asset["coreAttributes"]["businessMetaData"] = record["businessMetaData"]
    
    if "assignedLocation" in record:
        asset["coreAttributes"]["assignedLocation"] = record["assignedLocation"]
    
    if "businessApps" in record:
        asset["coreAttributes"]["businessApps"] = record["businessApps"]
    
    if "containers" in record:
        asset["coreAttributes"]["containers"] = record["containers"]
    
    if "customConnectorAttributes" in record:
        asset["coreAttributes"]["customConnectorAttributes"] = record["customConnectorAttributes"]
    
    return asset


def format_qualys_payload(
    records: list[dict[str, Any]],
    connector_name: str,
    connector_uuid: str | None = None,
    request_id: str | None = None
) -> dict[str, Any]:
    """Format a batch of records into the complete Qualys CSAM payload.
    
    Args:
        records: List of transformed asset records
        connector_name: Name of the connector (for logging/identification)
        connector_uuid: Qualys CSAM connector UUID (required)
        request_id: Request ID (generated if not provided)
    
    Returns:
        Complete Qualys CSAM payload with connectorMetaData and assetData
    
    Raises:
        ValueError: If connector_uuid is not provided
    """
    if connector_uuid is None:
        raise ValueError("connector_uuid is required for Qualys CSAM payload")
    
    if request_id is None:
        request_id = f"req-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    
    payload = {
        "connectorMetaData": {
            "requestId": request_id,
            "assetCount": len(records),
            "source": "WEBHOOK",  # Required by Qualys CSAM
            "connectorUuid": connector_uuid
        },
        "assetData": [format_asset_for_qualys(record) for record in records]
    }
    
    return payload
