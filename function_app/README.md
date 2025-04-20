# Blog Automation Functions

This directory contains the Azure Functions implementation for the blog automation pipeline, built using the Azure Functions v2 programming model.

## Architecture

The function app is structured around a pipeline with four main stages:

1. **Scheduler**: Triggers content generation based on timers or manual requests
2. **Processor**: Generates content based on topics and research
3. **Publisher**: Publishes content to WordPress sites
4. **Promoter**: Shares content on social media platforms

The functions communicate through Azure Storage Queues, allowing for a clean separation of concerns and resilient execution.

## Directory Structure

```
functions/
├── function_app.py       # Main entry point for the Functions app
├── host.json             # Function app configuration
├── local.settings.json   # Local settings and environment variables
├── requirements-functions.txt  # Python dependencies
├── scheduler/            # Scheduler functions
│   ├── __init__.py       # Functions logic
│   └── function.json     # Function bindings
├── processor/            # Content generation functions
│   ├── __init__.py
│   └── function.json
├── publisher/            # WordPress publishing functions
│   ├── __init__.py
│   └── function.json
└── promoter/             # Social media promotion functions
    ├── __init__.py
    └── function.json
```

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [Azure Functions Core Tools](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local)
- Azure CLI (for deployment)

### Setup

1. Run the setup script to create a virtual environment and install dependencies:

```bash
./setup-function-app.sh
```

2. Configure your local settings in `local.settings.json`

### Running Locally

```bash
func start
```

### Deployment

To deploy to Azure:

```bash
./deploy.sh <function-app-name> <resource-group>
```

Or use GitHub Actions by pushing to the main branch.

## Function Triggers

### Scheduler Functions

- **TriggerContentGeneration**: Timer-triggered function (every 6 hours)
- **ManualTrigger**: HTTP-triggered function for on-demand content generation

### Processor Functions

- **GenerateContent**: Queue-triggered function for content generation
- **ResearchTopics**: Queue-triggered function for topic research

### Publisher Functions

- **PublishContent**: Queue-triggered function for WordPress publishing
- **UploadImage**: Queue-triggered function for media uploading

### Promoter Functions

- **PromoteOnSocialMedia**: Queue-triggered function for social sharing
- **ScheduledPromotion**: Timer-triggered function for re-sharing content