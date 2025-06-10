# Radarr MCP Server

This server implements a comprehensive set of movie management tools for Radarr through the Model Context Protocol (MCP). Built with FastMCP, it provides automated movie discovery, monitoring, and download management capabilities.

## Design Rationale

This tool set was designed to provide complete movie management workflow automation:
- **Discovery**: Search and find movies to add to your collection
- **Management**: Add, monitor, and organize your movie library
- **Automation**: Handle downloads, queue management, and quality upgrades
- **Monitoring**: Track system health and download progress
- **Configuration**: Manage quality profiles, indexers, and system settings

## Implemented Tools

### Core Movie Management
1. **search_movies** - Search for movies using title or external IDs (IMDB, TMDB)
2. **add_movie** - Add movies with optional quality profiles and root folders (uses intelligent defaults)
3. **get_movies** - Retrieve current movie library with filtering options
4. **get_movie_details** - Get detailed information about specific movies including files and history

### Download Management
5. **search_movie_releases** - Find available releases for movies
6. **download_release** - Manually download specific releases
7. **get_download_queue** - View current download queue and progress
8. **manage_download_queue** - Control queue items (remove, retry, ignore)

### System Information
9. **get_system_defaults** - Get available quality profiles and root folders for reference
10. **get_wanted_movies** - List monitored but missing movies
11. **get_calendar** - View upcoming releases and monitoring calendar
12. **get_system_status** - Check system health, disk space, and configuration

### Advanced Configuration
13. **manage_indexers** - Configure and test indexer connections

### Resources
- **movie_collection** (`radarr://movies/{filter}`) - Dynamic access to movie collections
- **movie_details** (`radarr://movie/{movie_id}`) - Detailed movie information

## Quick Start

### Installation

```bash
# Clone the repository
git clone [repository-url]
cd radarr-mcp

# Install dependencies
pip install -e .

# Set up environment variables
cp .env.example .env
# Edit .env with your Radarr API credentials
```

### Docker Installation

```bash
# Using Docker Compose (recommended)
docker-compose up -d

# Or build and run manually
docker build -t radarr-mcp .
docker run -d \
  --name radarr-mcp-server \
  -p 4200:4200 \
  -e RADARR_URL=http://your-radarr:7878 \
  -e RADARR_API_KEY=your-api-key \
  radarr-mcp
```

### Configuration

1. **Get your Radarr API Key**:
   - Open Radarr web interface
   - Go to Settings → General → Security
   - Copy the API Key

2. **Configure environment variables**:
   ```bash
   RADARR_URL=http://localhost:7878
   RADARR_API_KEY=your-api-key-here
   ```

### Claude Desktop Configuration

Add the following to your Claude Desktop configuration file:

**MacOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`  
**Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "radarr-mcp": {
      "command": "python",
      "args": [
        "/absolute/path/to/radarr-mcp-server.py"
      ],
      "env": {
        "RADARR_API_KEY": "your-api-key-here",
        "RADARR_URL": "http://localhost:7878"
      }
    }
  }
}
```

### Cline Configuration (SSE Server)

In `cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "radarr-mcp-sse": {
      "url": "http://localhost:4200/mcp",
      "disabled": false,
      "autoApprove": ["search_movies", "get_movies", "get_system_status"],
      "timeout": 30
    }
  }
}
```

## Usage Examples

### Basic Movie Management

```python
# Search for a movie
await search_movies("The Matrix", year=1999)

# Add movie to library (uses defaults)
await add_movie("603")  # TMDB ID for The Matrix

# Add movie with specific settings
await add_movie("603", quality_profile_id=1, root_folder_path="/movies")

# Get all movies
await get_movies()

# Get only monitored movies
await get_movies(monitored=True)

# Get movie details
await get_movie_details(1, include_files=True, include_history=True)
```

### Download Management

```python
# Search for releases
await search_movie_releases(1, sort_by="seeders")

# Download a specific release
await download_release("release-guid-here", 1)

# Check download queue
await get_download_queue()

# Manage queue items
await manage_download_queue(123, "retry")
await manage_download_queue(124, "remove", remove_from_client=True)
```

### System Management

```python
# Check system defaults
await get_system_defaults()

# Get wanted movies
await get_wanted_movies()

# View calendar
await get_calendar("2024-01-01", "2024-01-31")

# Check system status
await get_system_status()

# Manage indexers
await manage_indexers("list")
await manage_indexers("test", indexer_id=1)
```

## API Authentication

The server uses Radarr's API key authentication. All requests include the `X-Api-Key` header with your configured API key.

## Error Handling

The server implements comprehensive error handling:
- **Connection errors**: Graceful handling of Radarr unavailability
- **Authentication errors**: Clear messages for invalid API keys
- **Rate limiting**: Respectful API usage patterns
- **Data validation**: Input validation and sanitization

## Troubleshooting

### Common Issues

1. **Connection refused**
   - Verify Radarr is running and accessible
   - Check RADARR_URL in environment variables
   - Ensure no firewall blocking the connection

2. **Authentication errors**
   - Verify API key is correct in Radarr settings
   - Check RADARR_API_KEY environment variable
   - Ensure API key has necessary permissions

3. **Tool execution failures**
   - Check server logs for detailed error messages
   - Verify Radarr API endpoints are accessible
   - Check Radarr version compatibility

4. **Movie not found errors**
   - Verify TMDB/IMDB IDs are correct
   - Check if movie exists in search results first
   - Ensure indexers are configured in Radarr

5. **Download issues**
   - Verify download clients are configured in Radarr
   - Check indexer connectivity and credentials
   - Review quality profile settings

### Log Analysis

Logs are written to both console and file (`radarr_mcp.log`):
- **INFO**: General operation information
- **DEBUG**: Detailed API interactions (use LOG_LEVEL=DEBUG)
- **ERROR**: Error conditions with stack traces

### Docker Troubleshooting

```bash
# Check container logs
docker logs radarr-mcp-server

# Access container shell
docker exec -it radarr-mcp-server /bin/bash

# Check health status
docker inspect radarr-mcp-server | grep Health
```

## Performance & Scalability

- **Caching**: Movie metadata cached for 10 minutes to reduce API calls
- **Pagination**: Large collections use pagination to prevent timeouts
- **Rate limiting**: Implements respectful API usage patterns
- **Connection pooling**: Efficient HTTP session management

## Security Considerations

- API key stored securely and never logged
- All requests use HTTPS when Radarr is configured with SSL
- Input validation prevents malicious data injection
- Rate limiting prevents API abuse

## Development

### Running in Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run with debug logging
LOG_LEVEL=DEBUG python radarr-mcp-server.py

# Run tests
pytest tests/

# Format code
black radarr-mcp-server.py

# Type checking
mypy radarr-mcp-server.py
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## FastMCP Implementation Notes

This server leverages FastMCP's advanced features:
- **Streamable HTTP transport** for web-based integration
- **Async/await patterns** for optimal performance
- **Resource-based data access** for dynamic content
- **Comprehensive error handling** with detailed logging
- **Type hints** for better development experience
# radarr-mcp
