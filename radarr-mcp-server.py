"""
MCP Server for Radarr
Implements movie management and automation tools for Radarr
Built with FastMCP following best practices from gofastmcp.com
Transport: Streamable HTTP
"""

import os
import sys
import json
import aiohttp
from fastmcp import FastMCP
from typing import Optional, Dict, Any, List
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Example logging setup for dual output:
import logging
import sys # Required for sys.stdout
from logging.handlers import RotatingFileHandler # For log rotation
from pathlib import Path # To place log file next to script

LOG_LEVEL_STR = os.getenv('LOG_LEVEL', 'INFO').upper()
NUMERIC_LOG_LEVEL = getattr(logging, LOG_LEVEL_STR, logging.INFO)
SCRIPT_DIR = Path(__file__).resolve().parent # Get script directory

# Define a base logger
logger = logging.getLogger("RadarrMCPServer") 
logger.setLevel(NUMERIC_LOG_LEVEL)
logger.propagate = False # Prevent root logger from duplicating messages if also configured

# Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(NUMERIC_LOG_LEVEL)
console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File Handler with Rotation (log file in the same directory as the script)
log_file_name = f"{os.getenv('RADARR_NAME', 'radarr').lower()}_mcp.log"
log_file_path = SCRIPT_DIR / log_file_name

# Example: Rotate logs at 5MB, keep 3 backup logs
file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
file_handler.setLevel(NUMERIC_LOG_LEVEL)
file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s - %(funcName)s - %(lineno)d - %(message)s')
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

logger.info(f"Logging initialized (console and file: {log_file_path}).")

# Load and validate environment variables
RADARR_URL = os.getenv('RADARR_URL', '').rstrip('/')
RADARR_API_KEY = os.getenv('RADARR_API_KEY', '')

logger.info(f"RADARR_URL loaded: {RADARR_URL[:20]}...")
logger.info(f"RADARR_API_KEY loaded: {'****' if RADARR_API_KEY else 'Not Found'}")
logger.info(f"RADARR_MCP_PORT set to: {os.getenv('RADARR_MCP_PORT', '4200')}")
logger.info(f"LOG_LEVEL set to: {os.getenv('LOG_LEVEL', 'INFO')}")

# Critical check for essential API credentials/URL
if not RADARR_URL or not RADARR_API_KEY:
    logger.error("RADARR_URL and RADARR_API_KEY must be set.")
    sys.exit(1)

# Initialize server
mcp = FastMCP(
    name="Radarr MCP Server",
    instructions="A comprehensive MCP server for managing movies through Radarr. Provides tools for searching, adding, monitoring, and downloading movies automatically."
)

# HTTP session for API requests
session = None

async def get_session():
    """Get or create HTTP session"""
    global session
    if session is None:
        session = aiohttp.ClientSession()
    return session

async def make_radarr_request(endpoint: str, method: str = "GET", data: Optional[Dict] = None) -> Dict[str, Any]:
    """Make authenticated request to Radarr API"""
    url = f"{RADARR_URL}/api/v3/{endpoint.lstrip('/')}"
    headers = {
        "X-Api-Key": RADARR_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        session = await get_session()
        if method.upper() == "GET":
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()
        elif method.upper() == "POST":
            async with session.post(url, headers=headers, json=data) as response:
                response.raise_for_status()
                return await response.json()
        elif method.upper() == "PUT":
            async with session.put(url, headers=headers, json=data) as response:
                response.raise_for_status()
                return await response.json()
        elif method.upper() == "DELETE":
            async with session.delete(url, headers=headers) as response:
                response.raise_for_status()
                return {"success": True, "status": response.status}
    except aiohttp.ClientError as e:
        logger.error(f"Radarr API request failed: {e}")
        raise Exception(f"Failed to communicate with Radarr: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in API request: {e}")
        raise

@mcp.tool()
async def search_movies(query: str, year: Optional[int] = None) -> Dict[str, Any]:
    """
    Search for movies using title or external IDs (IMDB, TMDB).
    
    Args:
        query: Movie title or external ID to search for
        year: Optional release year to narrow search results
    """
    logger.info(f"Searching for movies with query: {query}, year: {year}")
    try:
        search_term = f"{query} {year}" if year else query
        results = await make_radarr_request(f"movie/lookup?term={search_term}")
        
        processed_results = []
        for movie in results[:10]:  # Limit to top 10 results
            processed_results.append({
                "title": movie.get("title", "Unknown"),
                "year": movie.get("year"),
                "overview": movie.get("overview", "")[:200] + "..." if len(movie.get("overview", "")) > 200 else movie.get("overview", ""),
                "tmdb_id": movie.get("tmdbId"),
                "imdb_id": movie.get("imdbId"),
                "runtime": movie.get("runtime"),
                "status": movie.get("status"),
                "poster": movie.get("images", [{}])[0].get("url") if movie.get("images") else None,
                "genres": [g.get("name") for g in movie.get("genres", [])],
                "ratings": movie.get("ratings", {})
            })
        
        logger.debug(f"Found {len(processed_results)} movie results")
        return {
            "success": True,
            "results_count": len(processed_results),
            "movies": processed_results
        }
    except Exception as e:
        logger.error(f"Error searching movies: {e}", exc_info=True)
        return {"error": str(e)}

@mcp.tool()
async def add_movie(movie_id: str, quality_profile_id: Optional[int] = None, root_folder_path: Optional[str] = None, 
                   monitored: bool = True, search_on_add: bool = True) -> Dict[str, Any]:
    """
    Add a movie to Radarr for monitoring and automatic downloading.
    
    Args:
        movie_id: TMDB ID of the movie to add
        quality_profile_id: Quality profile to use (uses default if not specified)
        root_folder_path: Root folder for storage (uses default if not specified)
        monitored: Whether to monitor the movie for downloads
        search_on_add: Search for movie immediately after adding
    """
    logger.info(f"Adding movie with TMDB ID: {movie_id}")
    try:
        # First get movie details from lookup
        movie_lookup = await make_radarr_request(f"movie/lookup/tmdb?tmdbId={movie_id}")
        if not movie_lookup:
            return {"error": f"Movie with TMDB ID {movie_id} not found"}
        
        # Get defaults if not provided
        if quality_profile_id is None:
            profiles = await make_radarr_request("qualityprofile")
            quality_profile_id = profiles[0]["id"] if profiles else 1
            logger.info(f"Using default quality profile ID: {quality_profile_id}")
        
        if root_folder_path is None:
            root_folders = await make_radarr_request("rootfolder")
            root_folder_path = root_folders[0]["path"] if root_folders else "/movies"
            logger.info(f"Using default root folder: {root_folder_path}")
        
        # Prepare movie data
        movie_data = {
            "title": movie_lookup.get("title"),
            "year": movie_lookup.get("year"),
            "tmdbId": movie_lookup.get("tmdbId"),
            "imdbId": movie_lookup.get("imdbId"),
            "titleSlug": movie_lookup.get("titleSlug"),
            "images": movie_lookup.get("images", []),
            "runtime": movie_lookup.get("runtime"),
            "overview": movie_lookup.get("overview"),
            "genres": movie_lookup.get("genres", []),
            "ratings": movie_lookup.get("ratings", {}),
            "qualityProfileId": quality_profile_id,
            "rootFolderPath": root_folder_path,
            "monitored": monitored,
            "addOptions": {
                "searchForMovie": search_on_add
            }
        }
        
        result = await make_radarr_request("movie", "POST", movie_data)
        
        return {
            "success": True,
            "movie": {
                "id": result.get("id"),
                "title": result.get("title"),
                "year": result.get("year"),
                "status": result.get("status"),
                "monitored": result.get("monitored"),
                "quality_profile": result.get("qualityProfile", {}).get("name"),
                "root_folder": result.get("rootFolderPath")
            }
        }
    except Exception as e:
        logger.error(f"Error adding movie: {e}", exc_info=True)
        return {"error": str(e)}

@mcp.tool()
async def get_movies(monitored: Optional[bool] = None, status: Optional[str] = None, 
                    quality_profile_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Retrieve movies currently in the Radarr library with optional filtering.
    
    Args:
        monitored: Filter by monitoring status
        status: Filter by availability status (announced, inCinemas, released, etc.)
        quality_profile_id: Filter by quality profile ID
    """
    logger.info(f"Getting movies with filters - monitored: {monitored}, status: {status}")
    try:
        movies = await make_radarr_request("movie")
        
        # Apply filters
        if monitored is not None:
            movies = [m for m in movies if m.get("monitored") == monitored]
        if status:
            movies = [m for m in movies if m.get("status") == status]
        if quality_profile_id:
            movies = [m for m in movies if m.get("qualityProfileId") == quality_profile_id]
        
        processed_movies = []
        for movie in movies:
            movie_file = movie.get("movieFile", {})
            processed_movies.append({
                "id": movie.get("id"),
                "title": movie.get("title"),
                "year": movie.get("year"),
                "status": movie.get("status"),
                "monitored": movie.get("monitored"),
                "has_file": movie.get("hasFile", False),
                "quality_profile": movie.get("qualityProfile", {}).get("name"),
                "size_on_disk": movie.get("sizeOnDisk", 0),
                "overview": movie.get("overview", "")[:100] + "..." if len(movie.get("overview", "")) > 100 else movie.get("overview", ""),
                "file_info": {
                    "relative_path": movie_file.get("relativePath"),
                    "size": movie_file.get("size"),
                    "quality": movie_file.get("quality", {}).get("quality", {}).get("name")
                } if movie_file else None
            })
        
        return {
            "success": True,
            "total_count": len(processed_movies),
            "movies": processed_movies
        }
    except Exception as e:
        logger.error(f"Error getting movies: {e}", exc_info=True)
        return {"error": str(e)}

@mcp.tool()
async def get_movie_details(movie_id: int, include_files: bool = True, include_history: bool = False) -> Dict[str, Any]:
    """
    Get detailed information about a specific movie including files and history.
    
    Args:
        movie_id: Internal Radarr movie ID
        include_files: Include movie file details
        include_history: Include download history
    """
    logger.info(f"Getting details for movie ID: {movie_id}")
    try:
        movie = await make_radarr_request(f"movie/{movie_id}")
        
        result = {
            "id": movie.get("id"),
            "title": movie.get("title"),
            "year": movie.get("year"),
            "overview": movie.get("overview"),
            "status": movie.get("status"),
            "monitored": movie.get("monitored"),
            "has_file": movie.get("hasFile"),
            "runtime": movie.get("runtime"),
            "genres": [g.get("name") for g in movie.get("genres", [])],
            "ratings": movie.get("ratings", {}),
            "quality_profile": movie.get("qualityProfile", {}),
            "root_folder_path": movie.get("rootFolderPath"),
            "size_on_disk": movie.get("sizeOnDisk"),
            "tmdb_id": movie.get("tmdbId"),
            "imdb_id": movie.get("imdbId")
        }
        
        if include_files and movie.get("movieFile"):
            movie_file = movie["movieFile"]
            result["file_details"] = {
                "id": movie_file.get("id"),
                "relative_path": movie_file.get("relativePath"),
                "size": movie_file.get("size"),
                "date_added": movie_file.get("dateAdded"),
                "quality": movie_file.get("quality", {}),
                "media_info": movie_file.get("mediaInfo", {})
            }
        
        if include_history:
            history = await make_radarr_request(f"history/movie?movieId={movie_id}")
            result["history"] = [
                {
                    "event_type": h.get("eventType"),
                    "date": h.get("date"),
                    "quality": h.get("quality", {}),
                    "source_title": h.get("sourceTitle"),
                    "data": h.get("data", {})
                }
                for h in history.get("records", [])[:10]  # Last 10 events
            ]
        
        return {"success": True, "movie": result}
    except Exception as e:
        logger.error(f"Error getting movie details: {e}", exc_info=True)
        return {"error": str(e)}

@mcp.tool()
async def search_movie_releases(movie_id: int, sort_by: Optional[str] = "seeders") -> Dict[str, Any]:
    """
    Manually search for available releases of a specific movie.
    
    Args:
        movie_id: Internal Radarr movie ID
        sort_by: Sort releases by 'seeders', 'size', or 'quality'
    """
    logger.info(f"Searching releases for movie ID: {movie_id}")
    try:
        releases = await make_radarr_request(f"release?movieId={movie_id}")
        
        # Sort releases
        if sort_by == "seeders":
            releases.sort(key=lambda x: x.get("seeders", 0), reverse=True)
        elif sort_by == "size":
            releases.sort(key=lambda x: x.get("size", 0), reverse=True)
        elif sort_by == "quality":
            releases.sort(key=lambda x: x.get("quality", {}).get("quality", {}).get("id", 0), reverse=True)
        
        processed_releases = []
        for release in releases[:20]:  # Top 20 releases
            processed_releases.append({
                "guid": release.get("guid"),
                "title": release.get("title"),
                "size": release.get("size"),
                "age": release.get("age"),
                "seeders": release.get("seeders"),
                "leechers": release.get("leechers"),
                "quality": release.get("quality", {}).get("quality", {}).get("name"),
                "indexer": release.get("indexer"),
                "download_url": release.get("downloadUrl"),
                "approved": release.get("approved", False),
                "rejection_reasons": release.get("rejections", [])
            })
        
        return {
            "success": True,
            "releases_count": len(processed_releases),
            "releases": processed_releases
        }
    except Exception as e:
        logger.error(f"Error searching releases: {e}", exc_info=True)
        return {"error": str(e)}

@mcp.tool()
async def download_release(release_guid: str, movie_id: int) -> Dict[str, Any]:
    """
    Manually download a specific release for a movie.
    
    Args:
        release_guid: GUID of the release to download
        movie_id: Movie ID the release is for
    """
    logger.info(f"Downloading release {release_guid} for movie {movie_id}")
    try:
        download_data = {
            "guid": release_guid,
            "movieId": movie_id
        }
        
        result = await make_radarr_request("release", "POST", download_data)
        
        return {
            "success": True,
            "message": "Download started successfully",
            "release": result
        }
    except Exception as e:
        logger.error(f"Error downloading release: {e}", exc_info=True)
        return {"error": str(e)}

@mcp.tool()
async def get_download_queue(page: int = 1, page_size: int = 20, sort: Optional[str] = "progress") -> Dict[str, Any]:
    """
    View current download queue and progress.
    
    Args:
        page: Page number for pagination
        page_size: Number of items per page
        sort: Sort by 'progress', 'eta', or 'quality'
    """
    logger.info(f"Getting download queue - page: {page}, size: {page_size}")
    try:
        queue = await make_radarr_request(f"queue?page={page}&pageSize={page_size}&sortKey={sort}")
        
        processed_queue = []
        for item in queue.get("records", []):
            processed_queue.append({
                "id": item.get("id"),
                "movie_title": item.get("movie", {}).get("title"),
                "title": item.get("title"),
                "size": item.get("size"),
                "sizeleft": item.get("sizeleft"),
                "status": item.get("status"),
                "progress": item.get("progress", 0),
                "eta": item.get("estimatedCompletionTime"),
                "quality": item.get("quality", {}).get("quality", {}).get("name"),
                "protocol": item.get("protocol"),
                "download_client": item.get("downloadClient"),
                "output_path": item.get("outputPath"),
                "status_messages": [msg.get("title") for msg in item.get("statusMessages", [])]
            })
        
        return {
            "success": True,
            "total_records": queue.get("totalRecords", 0),
            "page": queue.get("page", 1),
            "page_size": queue.get("pageSize", page_size),
            "queue": processed_queue
        }
    except Exception as e:
        logger.error(f"Error getting download queue: {e}", exc_info=True)
        return {"error": str(e)}

@mcp.tool()
async def manage_download_queue(queue_id: int, action: str, remove_from_client: bool = False) -> Dict[str, Any]:
    """
    Control download queue items (remove, retry, ignore).
    
    Args:
        queue_id: Queue item ID
        action: Action to perform - "remove", "retry", or "ignore"
        remove_from_client: Also remove from download client (for remove action)
    """
    logger.info(f"Managing queue item {queue_id} with action: {action}")
    try:
        if action == "remove":
            params = f"removeFromClient={'true' if remove_from_client else 'false'}"
            result = await make_radarr_request(f"queue/{queue_id}?{params}", "DELETE")
        elif action == "retry":
            result = await make_radarr_request(f"queue/grab/{queue_id}", "POST")
        elif action == "ignore":
            # For ignore, we typically remove without removing from client
            result = await make_radarr_request(f"queue/{queue_id}?removeFromClient=false", "DELETE")
        else:
            return {"error": f"Invalid action: {action}. Use 'remove', 'retry', or 'ignore'"}
        
        return {
            "success": True,
            "action": action,
            "queue_id": queue_id,
            "result": result
        }
    except Exception as e:
        logger.error(f"Error managing queue: {e}", exc_info=True)
        return {"error": str(e)}

@mcp.tool()
async def get_system_defaults() -> Dict[str, Any]:
    """
    Get available quality profiles and root folders for reference.
    """
    logger.info("Getting system defaults (quality profiles and root folders)")
    try:
        profiles = await make_radarr_request("qualityprofile")
        root_folders = await make_radarr_request("rootfolder")
        
        return {
            "success": True,
            "quality_profiles": [
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "cutoff": p.get("cutoff", {}).get("name"),
                    "items": [item.get("quality", {}).get("name") for item in p.get("items", [])]
                }
                for p in profiles
            ],
            "root_folders": [
                {
                    "id": rf.get("id"),
                    "path": rf.get("path"),
                    "accessible": rf.get("accessible"),
                    "free_space": rf.get("freeSpace"),
                    "unmapped_folders": len(rf.get("unmappedFolders", []))
                }
                for rf in root_folders
            ]
        }
    except Exception as e:
        logger.error(f"Error getting system defaults: {e}", exc_info=True)
        return {"error": str(e)}

@mcp.tool()
async def get_wanted_movies(page: int = 1, page_size: int = 20) -> Dict[str, Any]:
    """
    List movies that are monitored but missing/not downloaded.
    
    Args:
        page: Page number for pagination
        page_size: Number of items per page
    """
    logger.info(f"Getting wanted movies - page: {page}, size: {page_size}")
    try:
        wanted = await make_radarr_request(f"wanted/missing?page={page}&pageSize={page_size}&sortKey=title")
        
        processed_wanted = []
        for movie in wanted.get("records", []):
            processed_wanted.append({
                "id": movie.get("id"),
                "title": movie.get("title"),
                "year": movie.get("year"),
                "status": movie.get("status"),
                "quality_profile": movie.get("qualityProfile", {}).get("name"),
                "size_on_disk": movie.get("sizeOnDisk"),
                "overview": movie.get("overview", "")[:100] + "..." if len(movie.get("overview", "")) > 100 else movie.get("overview", ""),
                "tmdb_id": movie.get("tmdbId"),
                "imdb_id": movie.get("imdbId")
            })
        
        return {
            "success": True,
            "total_records": wanted.get("totalRecords", 0),
            "page": wanted.get("page", 1),
            "wanted_movies": processed_wanted
        }
    except Exception as e:
        logger.error(f"Error getting wanted movies: {e}", exc_info=True)
        return {"error": str(e)}

@mcp.tool()
async def manage_indexers(action: str, indexer_id: Optional[int] = None, indexer_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Configure and test indexer connections.
    
    Args:
        action: Action to perform - "list", "test", "add", "update", "delete"
        indexer_id: Indexer ID (required for test, update, delete)
        indexer_data: Indexer configuration data (required for add, update)
    """
    logger.info(f"Managing indexers with action: {action}")
    try:
        if action == "list":
            indexers = await make_radarr_request("indexer")
            return {
                "success": True,
                "indexers": [
                    {
                        "id": idx.get("id"),
                        "name": idx.get("name"),
                        "implementation": idx.get("implementation"),
                        "enable_rss": idx.get("enableRss"),
                        "enable_automatic_search": idx.get("enableAutomaticSearch"),
                        "enable_interactive_search": idx.get("enableInteractiveSearch"),
                        "priority": idx.get("priority"),
                        "tags": idx.get("tags", [])
                    }
                    for idx in indexers
                ]
            }
        elif action == "test" and indexer_id:
            result = await make_radarr_request(f"indexer/test/{indexer_id}", "POST")
            return {"success": True, "test_result": result}
        elif action == "add" and indexer_data:
            result = await make_radarr_request("indexer", "POST", indexer_data)
            return {"success": True, "indexer": result}
        elif action == "update" and indexer_id and indexer_data:
            result = await make_radarr_request(f"indexer/{indexer_id}", "PUT", indexer_data)
            return {"success": True, "indexer": result}
        elif action == "delete" and indexer_id:
            result = await make_radarr_request(f"indexer/{indexer_id}", "DELETE")
            return {"success": True, "deleted": True}
        else:
            return {"error": "Invalid action or missing required parameters"}
    except Exception as e:
        logger.error(f"Error managing indexers: {e}", exc_info=True)
        return {"error": str(e)}

@mcp.tool()
async def get_calendar(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    """
    View upcoming movie releases and Radarr's monitoring calendar.
    
    Args:
        start_date: Start date in YYYY-MM-DD format (defaults to today)
        end_date: End date in YYYY-MM-DD format (defaults to 30 days from start)
    """
    logger.info(f"Getting calendar from {start_date} to {end_date}")
    try:
        # Default dates if not provided
        if not start_date:
            start_date = datetime.now().strftime("%Y-%m-%d")
        if not end_date:
            from datetime import timedelta
            end_dt = datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=30)
            end_date = end_dt.strftime("%Y-%m-%d")
        
        calendar = await make_radarr_request(f"calendar?start={start_date}&end={end_date}")
        
        processed_calendar = []
        for movie in calendar:
            processed_calendar.append({
                "id": movie.get("id"),
                "title": movie.get("title"),
                "year": movie.get("year"),
                "status": movie.get("status"),
                "monitored": movie.get("monitored"),
                "has_file": movie.get("hasFile"),
                "physical_release": movie.get("physicalRelease"),
                "digital_release": movie.get("digitalRelease"),
                "in_cinemas": movie.get("inCinemas"),
                "quality_profile": movie.get("qualityProfile", {}).get("name"),
                "overview": movie.get("overview", "")[:150] + "..." if len(movie.get("overview", "")) > 150 else movie.get("overview", "")
            })
        
        return {
            "success": True,
            "date_range": f"{start_date} to {end_date}",
            "movies_count": len(processed_calendar),
            "movies": processed_calendar
        }
    except Exception as e:
        logger.error(f"Error getting calendar: {e}", exc_info=True)
        return {"error": str(e)}

@mcp.tool()
async def get_system_status() -> Dict[str, Any]:
    """
    Check Radarr system health, disk space, and configuration.
    """
    logger.info("Getting system status")
    try:
        # Get multiple system endpoints
        status = await make_radarr_request("system/status")
        health = await make_radarr_request("health")
        disk_space = await make_radarr_request("diskspace")
        
        return {
            "success": True,
            "system_info": {
                "version": status.get("version"),
                "build_time": status.get("buildTime"),
                "is_debug": status.get("isDebug"),
                "is_production": status.get("isProduction"),
                "is_admin": status.get("isAdmin"),
                "is_user_interactive": status.get("isUserInteractive"),
                "startup_path": status.get("startupPath"),
                "app_data": status.get("appData"),
                "os_name": status.get("osName"),
                "os_version": status.get("osVersion"),
                "is_mono_runtime": status.get("isMonoRuntime"),
                "is_mono": status.get("isMono"),
                "is_linux": status.get("isLinux"),
                "is_windows": status.get("isWindows"),
                "mode": status.get("mode"),
                "branch": status.get("branch"),
                "authentication": status.get("authentication"),
                "sqlite_version": status.get("sqliteVersion"),
                "migration_version": status.get("migrationVersion"),
                "url_base": status.get("urlBase"),
                "runtime_version": status.get("runtimeVersion")
            },
            "health_checks": [
                {
                    "source": check.get("source"),
                    "type": check.get("type"),
                    "message": check.get("message"),
                    "wiki_url": check.get("wikiUrl")
                }
                for check in health
            ],
            "disk_space": [
                {
                    "path": disk.get("path"),
                    "label": disk.get("label"),
                    "free_space": disk.get("freeSpace"),
                    "total_space": disk.get("totalSpace")
                }
                for disk in disk_space
            ]
        }
    except Exception as e:
        logger.error(f"Error getting system status: {e}", exc_info=True)
        return {"error": str(e)}

# Resources
@mcp.resource("radarr://movies/{filter}")
async def movie_collection(filter: str = "all") -> str:
    """Dynamic access to movie collections with various filters"""
    try:
        if filter == "wanted":
            result = await get_wanted_movies()
        elif filter == "monitored":
            result = await get_movies(monitored=True)
        elif filter == "unmonitored":
            result = await get_movies(monitored=False)
        else:
            result = await get_movies()
        
        if result.get("success"):
            return json.dumps(result, indent=2)
        else:
            return json.dumps({"error": result.get("error", "Unknown error")})
    except Exception as e:
        return json.dumps({"error": str(e)})

@mcp.resource("radarr://movie/{movie_id}")
async def movie_details(movie_id: str) -> str:
    """Detailed information about a specific movie"""
    try:
        result = await get_movie_details(int(movie_id), include_files=True, include_history=True)
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})

# Cleanup session on shutdown
async def cleanup():
    """Clean up resources"""
    global session
    if session:
        await session.close()

# Transport-specific configuration
if __name__ == "__main__":
    import atexit
    import asyncio
    
    # Register cleanup
    atexit.register(lambda: asyncio.run(cleanup()))
    
    mcp.run(
        transport="streamable-http",
        host=os.getenv("RADARR_MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("RADARR_MCP_PORT", "4200")),
        path="/mcp",
        log_level=os.getenv("RADARR_LOG_LEVEL", "debug"),
    ) 