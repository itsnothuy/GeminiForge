from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import asdict
from typing import Dict, List, Optional

import google.generativeai as genai

logger = logging.getLogger(__name__) 

class GeminiAPIManager:
    """Manage five Gemini APIs with specialized roles"""
    
    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self.models = {}
        self.setup_models()
        
        # Define the system prompts for each API
        self.system_prompts = {
            "planner": """You are a senior business analyst and product manager. 
            Analyze requirements and create detailed specifications.
            
            RETURN ONLY VALID JSON with this structure:
            {
                "requirements": ["req1", "req2", "req3"],
                "user_stories": ["story1", "story2"],
                "acceptance_criteria": ["criteria1", "criteria2"],
                "timeline": "estimated timeline",
                "priority": "high/medium/low"
            }
            
            Keep strings short and avoid multiline content.""",
            
            "architect": """You are a system architect with 15+ years experience.
            Design scalable architectures and database schemas.
            
            RETURN ONLY VALID JSON with this structure:
            {
                "architecture_type": "microservices/monolith",
                "tech_stack": {
                    "backend": "framework name",
                    "frontend": "framework name",
                    "database": "database type"
                },
                "database_schema": "brief description",
                "api_design": "RESTful API design summary",
                "modules": ["module1", "module2", "module3"]
            }
            
            Keep all values as simple strings or arrays.""",
            
            "developer": """You are a senior full-stack developer.
            Generate COMPLETE, PRODUCTION-READY source code files.
            
            RETURN ONLY VALID JSON with this structure:
            {
                "modules": ["backend", "frontend", "database"],
                "file_structure": {
                    "backend/": "API server files",
                    "frontend/": "UI application files",
                    "database/": "Schema and migration files"
                },
                "dependencies": ["package1", "package2"],
                "code_files": {
                    "src/main.py": "FULL_SOURCE_CODE_HERE",
                    "package.json": "FULL_JSON_CONFIG_HERE"
                }
            }
            
            CRITICAL: code_files must contain COMPLETE, RUNNABLE source code, not descriptions.
            Generate real, functional code that can be executed immediately.
            Use proper imports, error handling, and best practices.
            Each file should be production-ready and fully functional.""",
            
            "reviewer": """You are a code review expert and QA engineer.
            Review code quality and generate COMPLETE test files with actual test code.
            
            RETURN ONLY VALID JSON with this structure:
            {
                "code_quality_score": 85,
                "issues": ["issue1", "issue2"],
                "suggestions": ["suggestion1", "suggestion2"],
                "test_files": {
                    "test_api.py": "COMPLETE_TEST_CODE_HERE",
                    "test_ui.js": "COMPLETE_TEST_CODE_HERE"
                },
                "security_report": "security assessment summary"
            }
            
            CRITICAL: test_files must contain COMPLETE, RUNNABLE test code, not descriptions.
            Generate real test functions with assertions, mocks, and proper test structure.""",
            
            "devops": """You are a DevOps engineer specializing in CI/CD and cloud deployment.
            Create COMPLETE deployment configuration files with actual content.
            
            RETURN ONLY VALID JSON with this structure:
            {
                "docker_files": {
                    "Dockerfile": "COMPLETE_DOCKERFILE_CONTENT_HERE",
                    "docker-compose.yml": "COMPLETE_COMPOSE_FILE_HERE"
                },
                "ci_cd_config": {
                    ".github/workflows/deploy.yml": "COMPLETE_GITHUB_ACTION_HERE"
                },
                "k8s_manifests": {
                    "deployment.yaml": "COMPLETE_K8S_DEPLOYMENT_HERE"
                },
                "deployment_guide": "step-by-step deployment instructions"
            }
            
            CRITICAL: All files must contain COMPLETE, FUNCTIONAL configuration content.
            Generate real Dockerfiles, YAML configs, and scripts that can be used immediately."""
        }
    
    def setup_models(self):
        """Initialize 5 Gemini models with different API keys"""
        for i, api_key in enumerate(self.api_keys):
            genai.configure(api_key=api_key)
            model_name = ['planner', 'architect', 'developer', 'reviewer', 'devops'][i]
            self.models[model_name] = genai.GenerativeModel('gemini-2.0-flash')
            logger.info(f"Initialized {model_name} model with API key {i+1}")
    
    async def call_api(self, model_name: str, prompt: str, context: ProjectContext, rag_context: str = "") -> Dict:
        """Call the API with error handling and retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Create the full prompt using the system prompt, project context, RAG context, and user request
                full_prompt = f"""
{self.system_prompts[model_name]}

PROJECT CONTEXT:
{json.dumps(asdict(context), indent=2, ensure_ascii=False)}

RAG CONTEXT (EXISTING PROJECT FILES):
{rag_context}

USER REQUEST:
{prompt}

CRITICAL JSON FORMATTING RULES:
1. For code_files: use "file_path": "COMPLETE_SOURCE_CODE" format
2. Include FULL, RUNNABLE source code in code_files values
3. DO NOT use descriptions - generate actual executable code
4. Use proper JSON escaping for multiline code (\\n for newlines)
5. Ensure all generated code is production-ready and functional
6. Response must be valid JSON - test it before sending

IMPORTANT: Review the RAG context to understand existing project structure and generate complete, working code.
"""
                
                model = self.models[model_name]
                
                # Configure generation settings to allow longer responses for source code
                generation_config = {
                    "temperature": 0.1,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 8192 if model_name != "developer" else 8192,  # Max tokens for code generation
                }
                
                response = model.generate_content(full_prompt, generation_config=generation_config)
                
                # Parse the JSON response using multiple strategies
                response_text = response.text.strip()
                result = self.parse_json_response(response_text, model_name, attempt)
                
                if result:
                    logger.info(f"✅ {model_name} API call successful")
                    return result
                    
            except Exception as e:
                logger.error(f"❌ API call error in {model_name}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    # Return the default structure instead of raising an exception
                    return self.get_default_structure(model_name)
        logger.error(f"⚠️ Falling back to default structure for {model_name} after all retries")
        return self.get_default_structure(model_name)

    
    def parse_json_response(self, response_text: str, model_name: str, attempt: int) -> Optional[Dict]:
        """Parse the JSON response using multiple strategies"""
        parsing_strategies = [
            self.parse_clean_json,
            self.parse_markdown_json, 
            self.parse_partial_json,
            self.parse_line_by_line_json
        ]
        
        for i, strategy in enumerate(parsing_strategies):
            try:
                result = strategy(response_text)
                if result:
                    logger.info(f"✅ JSON parsed using strategy {i+1} for {model_name}")
                    return result
            except Exception as e:
                logger.debug(f"Strategy {i+1} failed for {model_name}: {e}")
                continue
        
        logger.error(f"❌ All JSON parsing strategies failed for {model_name} (attempt {attempt+1})")
        return None
    
    def parse_clean_json(self, text: str) -> Dict:
        """Parse JSON directly from clean text"""
        return json.loads(text.strip())
    
    def parse_markdown_json(self, text: str) -> Dict:
        """Parse JSON from markdown blocks"""
        if '```json' in text:
            json_content = text.split('```json')[1].split('```')[0].strip()
            return json.loads(json_content)
        elif '```' in text:
            json_content = text.split('```')[1].split('```')[0].strip()
            return json.loads(json_content)
        raise ValueError("No markdown JSON found")
    
    def parse_partial_json(self, text: str) -> Dict:
        """Locate and parse the first JSON object"""
        start = text.find('{')
        if start == -1:
            raise ValueError("No JSON object found")
        
        brace_count = 0
        end = start
        
        for i in range(start, len(text)):
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end = i + 1
                    break
        
        if brace_count != 0:
            raise ValueError("Incomplete JSON object")
        
        json_str = text[start:end]
        return json.loads(json_str)
    
    def parse_line_by_line_json(self, text: str) -> Dict:
        """Parse JSON line by line to find errors"""
        lines = text.split('\n')
        json_lines = []
        in_json = False
        
        for line in lines:
            if line.strip().startswith('{') or in_json:
                in_json = True
                json_lines.append(line)
                if line.strip().endswith('}') and line.count('}') >= line.count('{'):
                    break
        
        if not json_lines:
            raise ValueError("No JSON content found")
        
        json_str = '\n'.join(json_lines)
        
        # Fix common JSON issues
        json_str = self.fix_common_json_issues(json_str)
        
        return json.loads(json_str)
    
    def fix_common_json_issues(self, json_str: str) -> str:
        """Fix common JSON formatting issues"""
        # Remove trailing commas
        json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
        
        # Fix unescaped quotes in strings (basic fix)  
        json_str = re.sub(r'(?<!\\)"(?![,\]\}:\s])', r'\\"', json_str)
        
        # Remove control characters
        json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
        
        return json_str
    
    def get_default_structure(self, model_name: str) -> Dict:
        """Return the default structure when JSON parsing fails"""
        default_structures = {
            "planner": {
                "requirements": ["Parse failed - manual review needed"],
                "user_stories": ["Parse failed - manual review needed"],
                "acceptance_criteria": ["Parse failed - manual review needed"],
                "timeline": "Parse failed - manual review needed",
                "status": "partial_failure"
            },
            "architect": {
                "architecture_type": "microservices", 
                "tech_stack": {
                    "backend": "FastAPI",
                    "frontend": "React",
                    "database": "PostgreSQL"
                },
                "database_schema": "Parse failed - manual review needed",
                "api_design": "Parse failed - manual review needed",
                "status": "partial_failure"
            },
            "developer": {
                "modules": ["backend", "frontend", "database"],
                "file_structure": {
                    "backend/": "FastAPI application structure",
                    "frontend/": "React application structure", 
                    "database/": "Database migration files"
                },
                "code_files": {
                    "README.md": "# Project generated with parsing issues\\nManual review required.",
                    "main.py": "# Basic FastAPI app\\nfrom fastapi import FastAPI\\napp = FastAPI()\\n\\n@app.get('/')\\ndef read_root():\\n    return {'Hello': 'World'}",
                    "requirements.txt": "fastapi\\nuvicorn\\nsqlalchemy\\npsycopg2"
                },
                "dependencies": ["fastapi", "react", "postgresql"],
                "status": "partial_failure"
            },
            "reviewer": {
                "code_quality_score": 0,
                "issues": ["JSON parsing failed - manual code review required"],
                "suggestions": ["Fix JSON parsing issues", "Manual code review needed"],
                "test_files": {
                    "test_main.py": "import pytest\\nfrom fastapi.testclient import TestClient\\nfrom main import app\\n\\nclient = TestClient(app)\\n\\ndef test_read_root():\\n    response = client.get('/')\\n    assert response.status_code == 200\\n    assert response.json() == {'Hello': 'World'}"
                },
                "security_report": "Parse failed - manual review needed",
                "status": "partial_failure"
            },
            "devops": {
                "docker_files": {
                    "Dockerfile": "FROM python:3.9\\nWORKDIR /app\\nCOPY requirements.txt .\\nRUN pip install -r requirements.txt\\nCOPY . .\\nEXPOSE 8000\\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]",
                    "docker-compose.yml": "version: '3.8'\\nservices:\\n  web:\\n    build: .\\n    ports:\\n      - \"8000:8000\"\\n  db:\\n    image: postgres:13\\n    environment:\\n      POSTGRES_DB: app\\n      POSTGRES_USER: user\\n      POSTGRES_PASSWORD: password"
                },
                "ci_cd_config": {
                    ".github/workflows/deploy.yml": "name: Deploy\\non:\\n  push:\\n    branches: [main]\\njobs:\\n  deploy:\\n    runs-on: ubuntu-latest\\n    steps:\\n      - uses: actions/checkout@v2\\n      - name: Build and Deploy\\n        run: |\\n          docker build -t app .\\n          docker run -d -p 8000:8000 app"
                },
                "k8s_manifests": {
                    "deployment.yaml": "apiVersion: apps/v1\\nkind: Deployment\\nmetadata:\\n  name: app\\nspec:\\n  replicas: 3\\n  selector:\\n    matchLabels:\\n      app: app\\n  template:\\n    metadata:\\n      labels:\\n        app: app\\n    spec:\\n      containers:\\n      - name: app\\n        image: app:latest\\n        ports:\\n        - containerPort: 8000"
                },
                "deployment_guide": "Parse failed - manual review needed",
                "status": "partial_failure"
            }
        }
        
        return default_structures.get(model_name, {"error": "Unknown model", "status": "failure"})