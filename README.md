# Multi-Blog Content Generation and Publishing Pipeline

This project implements a fully automated, theme-aware, multi-blog content generation and publishing pipeline on Azure using serverless functions. The system automatically researches trending topics, generates high-quality blog content, and publishes it to WordPress sites with AdSense integration.

## Architecture

The system uses Azure Functions with a combination of timer and blob triggers to create a serverless content generation pipeline:

1. **Scheduler Function** (Timer Trigger): Runs on a schedule to initiate the content generation process for blogs based on their publishing frequency.

2. **Processor Function** (Blob Trigger): Triggered when a new blog task is created. Researches trending topics using PyTrends, generates content using Azure OpenAI, and prepares it for publishing.

3. **Publisher Function** (Blob Trigger): Triggered when new content is ready. Publishes the content to WordPress using its REST API and integrates AdSense ads if configured.

4. **Setup Function** (HTTP Trigger): Provides an API endpoint for initializing new blog configurations.

## Infrastructure

The infrastructure is defined using Bicep templates for Infrastructure as Code (IaC):

- **Azure Functions**: Hosts the serverless application
- **Azure Storage**: Stores blog tasks, content, and results
- **Azure Key Vault**: Securely stores API keys and credentials
- **Application Insights**: Provides monitoring and logging

## Getting Started

### Prerequisites

- Azure subscription
- Azure CLI installed
- Python 3.9 or later
- Azure Functions Core Tools
- VS Code with Azure Functions extension (recommended)

### Deployment

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/blog-automation.git
   cd blog-automation
   ```

2. Set up Azure credentials:
   ```bash
   az login
   ```

3. Run the deployment script:
   ```bash
   python deploy.py
   ```

4. Deploy the Azure Functions and infrastructure:
   ```bash
   cd infra
   az deployment group create --resource-group my-replit-rg --template-file main.bicep
   ```

### Configuration

After deployment, you need to:

1. Configure API keys in Azure Key Vault:
   - OpenAI API key
   - GoDaddy API credentials (if domain suggestions are needed)

2. Set up your first blog by making a POST request to the setup function:
   ```bash
   curl -X POST https://your-function-app.azurewebsites.net/api/setup \
     -H "Content-Type: application/json" \
     -d '{
       "blog_name": "My Tech Blog",
       "theme": "technology",
       "wordpress_url": "https://mytechblog.com",
       "wordpress_username": "admin",
       "wordpress_app_password": "xxxx xxxx xxxx xxxx",
       "tone": "professional",
       "target_audience": "tech enthusiasts",
       "publishing_frequency": "weekly",
       "adsense_publisher_id": "pub-1234567890",
       "adsense_ad_slots": ["1234567890", "0987654321"]
     }'
   ```

## Features

- **Theme-aware Content Generation**: Creates content specific to each blog's theme and target audience
- **Trending Topic Research**: Uses PyTrends to identify popular topics
- **SEO Optimization**: Generates SEO metadata for better search engine rankings
- **WordPress Integration**: Publishes directly to WordPress via REST API
- **AdSense Integration**: Automatically inserts AdSense ads at optimal positions
- **Domain Suggestions**: Provides domain name recommendations via GoDaddy API
- **Scheduling**: Customizable publishing frequency for each blog

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
