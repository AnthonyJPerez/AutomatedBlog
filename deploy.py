import os
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient

credential = ClientSecretCredential(
    tenant_id=os.environ["AZURE_TENANT_ID"],
    client_id=os.environ["AZURE_CLIENT_ID"],
    client_secret=os.environ["AZURE_CLIENT_SECRET"]
)

subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
resource_client = ResourceManagementClient(credential, subscription_id)

RESOURCE_GROUP = "my-replit-rg"
LOCATION = "eastus"

# Create resource group
resource_client.resource_groups.create_or_update(
    RESOURCE_GROUP,
    {"location": LOCATION}
)

print(f"Resource group '{RESOURCE_GROUP}' created or updated successfully in {LOCATION}")
