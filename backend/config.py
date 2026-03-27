"""
Configuration management for AI MCQ Generator
Centralizes all configurable parameters
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Configuration
    groq_api_key: str
    groq_model: str = "llama-3.3-70b-versatile"
    groq_api_url: str = "https://api.groq.com/openai/v1/chat/completions"
    
    # Generation Parameters
    generation_buffer: float = 0.20  # 20% buffer for malformed questions
    max_retries: int = 3
    retry_delay_seconds: int = 3
    rate_limit_delay_seconds: int = 5
    
    # File Handling
    max_file_size_mb: int = 10
    allowed_extensions: set = {"pdf", "txt", "docx"}
    chunk_size_bytes: int = 8192  # 8KB chunks for streaming
    
    # PDF Generation
    pdf_font_size: int = 9
    pdf_margin_mm: int = 15
    
    # Rate Limiting
    rate_limit_requests_per_minute: int = 5
    rate_limit_requests_per_hour: int = 100
    
    # Validation Limits
    min_questions: int = 1
    max_questions: int = 100
    min_cos: int = 1
    max_cos: int = 20
    max_co_length: int = 500
    max_topic_name_length: int = 50
    
    # LLM Parameters
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.7
    llm_timeout_seconds: int = 120
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton instance
settings = Settings()
