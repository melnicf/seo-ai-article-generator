"""AI article generator for Lemon.io /hire/ landing pages.

Package structure:
    src/config.py           – paths, API keys, model settings, internal links
    src/loaders/            – data loading (templates, Search Console, Clearscope, case studies)
    src/pipeline/           – article generation (header selection, prompts, Claude API)
    src/validation/         – quality checks, grading, and report formatting
"""
