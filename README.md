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

## Documentation

Comprehensive documentation for the system is available in the `/docs` directory:

- [Automated Multi-Blog Content Pipeline Documentation](docs/automated_blog_system.md): Contains detailed information about system architecture, components, and workflows with interactive Mermaid diagrams.

The documentation includes:
- System architecture diagrams
- State machine workflows
- Component interaction sequences
- Data storage structure
- Integration points
- Detailed configuration examples

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

3. Run the consolidated deployment script:
   ```bash
   # For development environment
   python deploy-consolidated.py --resource-group "blogauto-dev-rg" --deploy-wordpress
   
   # For production environment (westus region recommended)
   python deploy-consolidated.py --resource-group "blogauto-prod-rg" --location "westus" --environment "prod" --deploy-wordpress
   ```
   
4. Access the admin portal:
   ```
   https://blogauto-{env}-function.azurewebsites.net/
   ```

### Configuration

After deployment, you can use either the admin portal or API for configuration:

1. **Admin Portal Interface** (Recommended):
   - Navigate to `https://blogauto-{env}-function.azurewebsites.net/`
   - Use the web interface to:
     - Configure API keys and credentials
     - Set up new blogs
     - Manage existing blogs
     - Monitor content generation
     - View analytics data
     - Edit JSON configuration files directly

2. **API Configuration** (Advanced):
   - Configure API keys in Azure Key Vault:
     - OpenAI API key
     - Anthropic API key (if using Claude models)
     - Social media credentials
     - WordPress credentials

3. **Set up your first blog** through either:
   - Admin portal form (recommended)
   - API request:
     ```bash
     curl -X POST https://blogauto-{env}-function.azurewebsites.net/api/blog \
       -H "Content-Type: application/json" \
       -d '{
         "blog_name": "My Tech Blog",
         "description": "A blog about the latest in technology",
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
- **Trending Topic Research**: Uses PyTrends and web scraping to identify popular topics
- **Competitor Analysis**: Tracks and analyzes competitors' content to identify gaps and opportunities
- **Keyword Opportunity Finder**: Identifies high-value keywords your competitors are targeting
- **SEO Optimization**: Generates SEO-optimized metadata and content structure
- **WordPress Integration**: Publishes directly to WordPress via REST API with Multisite support
- **Domain Mapping**: Advanced domain management for WordPress Multisite setups
- **AI Cost Optimization**: Token counting, prompt refinement, and caching for efficient AI usage
- **Social Media Integration**: Automatically promotes content on multiple platforms
- **Analytics Dashboard**: Comprehensive tracking of traffic, engagement, and monetization
- **AdSense Integration**: Automatically inserts AdSense ads at optimal positions
- **Domain Suggestions**: Provides domain name recommendations via GoDaddy API
- **Image Generation**: Creates relevant featured images for blog posts
- **Scheduling**: Customizable publishing frequency for each blog

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
