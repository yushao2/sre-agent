"""Configuration management for AI SRE Agent."""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM Settings
    anthropic_api_key: str = Field(..., description="Anthropic API key")
    model_name: str = Field(default="claude-sonnet-4-20250514", description="Model to use")
    
    # Jira Settings
    jira_url: str = Field(default="", description="Jira instance URL")
    jira_username: str = Field(default="", description="Jira username/email")
    jira_api_token: str = Field(default="", description="Jira API token")
    
    # Confluence Settings
    confluence_url: str = Field(default="", description="Confluence instance URL")
    confluence_username: str = Field(default="", description="Confluence username/email")
    confluence_api_token: str = Field(default="", description="Confluence API token")
    
    # GitLab Settings
    gitlab_url: str = Field(default="https://gitlab.com", description="GitLab instance URL")
    gitlab_token: str = Field(default="", description="GitLab personal access token")
    
    # RAG Settings
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2", 
        description="Sentence transformer model for embeddings"
    )
    chroma_persist_dir: str = Field(
        default="./data/chroma",
        description="Directory to persist ChromaDB"
    )
    chunk_size: int = Field(default=1000, description="Text chunk size for RAG")
    chunk_overlap: int = Field(default=200, description="Overlap between chunks")
    
    # MCP Settings
    mcp_server_timeout: int = Field(default=30, description="MCP server timeout in seconds")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Global settings instance
settings = Settings()
