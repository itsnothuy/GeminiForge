from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .context import ProjectContext
from .rag_manager import RAGManager
from .api_manager import GeminiAPIManager

logger = logging.getLogger(__name__)


class ProjectWorkflowManager:
    """Manage the project’s main workflow"""
    
    def __init__(self, api_manager: GeminiAPIManager, project_name: str):
        self.api_manager = api_manager
        self.project_name = project_name
        self.context = ProjectContext(project_name=project_name)
        self.project_dir = Path(f"projects/{project_name}")
        self.rag_manager = RAGManager(self.project_dir)
        self.setup_project_structure()
        
        # Load existing context if present
        self.load_existing_context()
    
    def setup_project_structure(self):
        """Create the project directory structure"""
        directories = [
            "01_requirements",
            "02_architecture", 
            "03_code",
            "04_tests",
            "05_deployment",
            "logs"
        ]
        
        for dir_name in directories:
            (self.project_dir / dir_name).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"📁 Created project structure for {self.project_name}")
    
    def load_existing_context(self):
        """Load existing project context if present"""
        context_file = self.project_dir / "project_context.json"
        if context_file.exists():
            try:
                with open(context_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Restore context
                self.context.requirements = data.get('requirements')
                self.context.architecture = data.get('architecture')
                self.context.codebase = data.get('codebase')
                self.context.test_results = data.get('test_results')
                self.context.deployment = data.get('deployment')
                self.context.current_stage = data.get('current_stage', 'not_started')
                
                logger.info(f"📂 Loaded existing context from {context_file}")
                logger.info(f"🔄 Current stage: {self.context.current_stage}")
                
            except Exception as e:
                logger.warning(f"⚠️ Could not load existing context: {e}")
    
    def save_context(self):
        """Save the current context to a file"""
        context_file = self.project_dir / "project_context.json"
        with open(context_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.context), f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Saved context to {context_file}")
    
    def save_stage_output(self, stage: str, data: Dict, filename: str = None):
        """Save each stage’s output to a file"""
        if not filename:
            filename = f"{stage}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        stage_dirs = {
            "requirements": "01_requirements",
            "architecture": "02_architecture", 
            "code": "03_code",
            "review": "04_tests",
            "deployment": "05_deployment"
        }
        
        file_path = self.project_dir / stage_dirs[stage] / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Saved {stage} output to {file_path}")
        return file_path
    
    async def stage_1_requirements(self, user_input: str):
        """Stage 1: Requirements analysis"""
        logger.info("🎯 Stage 1: Requirements Analysis")
        self.context.current_stage = "requirements"
        
        # Get RAG context
        rag_context = self.rag_manager.get_context_for_stage("requirements")
        
        prompt = f"""
        Analyze this project request and create detailed requirements:
        
        {user_input}
        
        Create comprehensive requirements document with user stories and acceptance criteria.
        Review any existing requirements in the RAG context and build upon them.
        """
        
        result = await self.api_manager.call_api("planner", prompt, self.context, rag_context)
        self.context.requirements = result
        
        # Save file and context
        self.save_stage_output("requirements", result)
        self.save_context()
        return result
    
    async def stage_2_architecture(self):
        """Stage 2: Architecture design"""
        logger.info("🏗 Stage 2: Architecture Design")
        self.context.current_stage = "architecture"
        
        # Get RAG context
        rag_context = self.rag_manager.get_context_for_stage("architecture")
        
        prompt = """
        Based on the requirements, design a complete system architecture.
        Include technology stack, database design, API structure, and system diagrams.
        Consider scalability, security, and performance requirements.
        Review existing architecture files and build upon or refine them.
        """
        
        result = await self.api_manager.call_api("architect", prompt, self.context, rag_context)
        self.context.architecture = result
        
        self.save_stage_output("architecture", result)
        self.save_context()
        return result
    
    async def stage_3_code_generation(self):
        """Stage 3: Code generation (can run in parallel)"""
        logger.info("💻 Stage 3: Code Generation")
        self.context.current_stage = "code"
        
        # Scan existing files first
        self.rag_manager.scan_project_files()
        
        # Fetch the list of modules from the architecture
        modules = self.context.architecture.get('modules', ['backend', 'frontend', 'database'])
        
        # Get RAG context
        rag_context = self.rag_manager.get_context_for_stage("code")
        
        # Run prompts for each module in parallel
        tasks = []
        for module in modules:
            prompt = f"""
            Create file structure and basic setup for the {module} module.
            
            Focus on:
            - Directory structure
            - Key configuration files  
            - Main entry points
            - Dependencies list
            
            DO NOT include full source code in JSON - only file descriptions and short configs.
            Review existing code structure in RAG context and continue from where it left off.
            """
            
            task = self.generate_module_code(module, prompt, rag_context)
            tasks.append(task)
        
        # Wait for all modules to finish
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"❌ Error in parallel code generation: {e}")
            results = [self.api_manager.get_default_structure("developer") for _ in modules]
        
        # Combine results
        combined_result = {
            "modules": {},
            "file_structure": {},
            "dependencies": [],
            "status": "completed"
        }
        
        for i, module in enumerate(modules):
            if isinstance(results[i], Exception):
                logger.error(f"❌ Module {module} generation failed: {results[i]}")
                combined_result["modules"][module] = self.api_manager.get_default_structure("developer")
                combined_result["status"] = "partial_failure"
            else:
                combined_result["modules"][module] = results[i]
                
                # Merge dependencies
                module_deps = results[i].get("dependencies", [])
                combined_result["dependencies"].extend(module_deps)
        
        # Remove duplicate dependencies
        combined_result["dependencies"] = list(set(combined_result["dependencies"]))
        
        self.context.codebase = combined_result
        self.save_stage_output("code", combined_result)
        
        # Create the actual code files
        await self.create_code_files(combined_result)
        
        # Update RAG index after creating files
        self.rag_manager.scan_project_files()
        self.rag_manager.save_rag_index()
        
        self.save_context()
        return combined_result
    
    async def generate_module_code(self, module_name: str, prompt: str, rag_context: str):
        """Generate code for a specific module"""
        logger.info(f"⚙️ Generating code for {module_name}")
        
        result = await self.api_manager.call_api("developer", prompt, self.context, rag_context)
        return result
    
    async def create_code_files(self, codebase_data: Dict):
        """Create real code files from JSON data"""
        code_dir = self.project_dir / "03_code"
        
        for module_name, module_data in codebase_data.get("modules", {}).items():
            module_dir = code_dir / module_name
            module_dir.mkdir(exist_ok=True)
            
            # Create files from code_files
            if "code_files" in module_data:
                for file_path, file_content in module_data["code_files"].items():
                    full_path = module_dir / file_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(full_path, 'w', encoding='utf-8') as f:
                        f.write(file_content)
                    
                    logger.info(f"📄 Created {full_path}")
    
    async def stage_4_review_and_test(self):
        """Stage 4: Code review and test generation"""
        logger.info("🧪 Stage 4: Code Review & Testing")
        self.context.current_stage = "review"
        
        # Scan existing files first
        self.rag_manager.scan_project_files()
        
        # Get RAG context
        rag_context = self.rag_manager.get_context_for_stage("review")
        
        prompt = """
        Review the generated codebase and create COMPLETE test files:
        1. Unit tests with full test functions
        2. Integration tests with real API calls
        3. End-to-end tests with complete scenarios
        4. Performance tests with benchmarks
        5. Security tests with vulnerability checks
        6. Generate COMPLETE, RUNNABLE test code - not descriptions
        
        Use the RAG context to understand the current codebase and create comprehensive tests.
        Include proper test setup, teardown, mocks, and assertions.
        """
        
        result = await self.api_manager.call_api("reviewer", prompt, self.context, rag_context)
        self.context.test_results = result
        
        self.save_stage_output("review", result)
        
        # Generate test files if present
        if "test_files" in result:
            await self.create_test_files(result["test_files"])
        
        self.save_context()
        return result
    
    async def create_test_files(self, test_data: Dict):
        """Create test files"""
        test_dir = self.project_dir / "04_tests"
        
        for file_path, file_content in test_data.items():
            full_path = test_dir / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(file_content)
            
            logger.info(f"🧪 Created test file {full_path}")
    
    async def stage_5_deployment(self):
        """Stage 5: Create deployment configurations"""
        logger.info("🔄 Stage 5: Deployment & DevOps")
        self.context.current_stage = "deployment"
        
        # Scan existing files first
        self.rag_manager.scan_project_files()
        
        # Get RAG context
        rag_context = self.rag_manager.get_context_for_stage("deployment")
        
        prompt = """
        Create COMPLETE deployment configuration files:
        1. Full Dockerfiles for each service with multi-stage builds
        2. Complete docker-compose.yml with all services and volumes
        3. Complete Kubernetes manifests (deployments, services, ingress)
        4. Full GitHub Actions workflow with all steps
        5. Complete deployment scripts and documentation
        6. Monitoring and logging configurations (Prometheus, Grafana)
        7. Environment-specific configurations (dev, staging, prod)
        
        Generate COMPLETE, FUNCTIONAL configuration files that can be used immediately.
        Use the RAG context to understand the complete project structure.
        """
        
        result = await self.api_manager.call_api("devops", prompt, self.context, rag_context)
        self.context.deployment = result
        
        self.save_stage_output("deployment", result)
        
        # Create deployment files with safe path handling
        await self.create_deployment_files_safe(result)
        
        self.save_context()
        return result
    
    async def create_deployment_files_safe(self, deployment_data: Dict):
        """Create deployment files with safe path handling"""
        deploy_dir = self.project_dir / "05_deployment"
        
        file_mappings = {
            "docker_files": "docker",
            "ci_cd_config": "ci-cd", 
            "k8s_manifests": "kubernetes"
        }
        
        for data_key, folder_name in file_mappings.items():
            if data_key in deployment_data:
                folder_path = deploy_dir / folder_name
                folder_path.mkdir(parents=True, exist_ok=True)  # Ensure parents exist
                
                files_data = deployment_data[data_key]
                if isinstance(files_data, dict):
                    for file_name, file_content in files_data.items():
                        # Safe file path handling
                        try:
                            # Clean file name and create safe path
                            safe_file_name = re.sub(r'[<>:"/\\|?*]', '_', file_name)
                            file_path = folder_path / safe_file_name
                            
                            # Ensure parent directory exists
                            file_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            # Write file content
                            content = file_content if isinstance(file_content, str) else str(file_content)
                            
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(content)
                            
                            logger.info(f"🚀 Created deployment file {file_path}")
                            
                        except Exception as e:
                            logger.error(f"❌ Failed to create deployment file {file_name}: {e}")
                            # Create a simple text file with the error
                            error_file = folder_path / f"error_{safe_file_name}.txt"
                            with open(error_file, 'w', encoding='utf-8') as f:
                                f.write(f"Error creating {file_name}: {e}\n\nOriginal content:\n{file_content}")
                            logger.info(f"📝 Created error file {error_file}")
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """Get the current workflow status"""
        stages = {
            "requirements": self.context.requirements is not None,
            "architecture": self.context.architecture is not None,
            "code": self.context.codebase is not None,
            "review": self.context.test_results is not None,
            "deployment": self.context.deployment is not None
        }
        
        completed_stages = sum(stages.values())
        total_stages = len(stages)
        
        return {
            "current_stage": self.context.current_stage,
            "stages": stages,
            "progress": f"{completed_stages}/{total_stages}",
            "percentage": (completed_stages / total_stages) * 100,
            "project_dir": str(self.project_dir),
            "last_updated": datetime.now().isoformat()
        }
    
    async def resume_workflow(self, user_input: str = None):
        """Resume the workflow from the current stage"""
        status = self.get_workflow_status()
        logger.info(f"🔄 Resuming workflow from stage: {self.context.current_stage}")
        logger.info(f"📊 Progress: {status['progress']} ({status['percentage']:.1f}%)")
        
        # Determine next stage to run
        if not self.context.requirements:
            if not user_input:
                raise ValueError("User input required for requirements stage")
            await self.stage_1_requirements(user_input)
        
        if not self.context.architecture:
            await self.stage_2_architecture()
        
        if not self.context.codebase:
            await self.stage_3_code_generation()
        
        if not self.context.test_results:
            await self.stage_4_review_and_test()
        
        if not self.context.deployment:
            await self.stage_5_deployment()
        
        # Mark as completed
        self.context.current_stage = "completed"
        self.save_context()
        
        logger.info("✅ Workflow completed successfully!")
        return self.context
    
    async def run_full_workflow(self, user_input: str):
        """Run the full workflow"""
        logger.info(f"🚀 Starting full workflow for project: {self.project_name}")
        
        try:
            # Check if workflow is already in progress
            if self.context.current_stage != "not_started":
                logger.info(f"🔄 Resuming existing workflow from stage: {self.context.current_stage}")
                return await self.resume_workflow(user_input)
            
            # Stage 1: Requirements
            await self.stage_1_requirements(user_input)
            
            # Stage 2: Architecture  
            await self.stage_2_architecture()
            
            # Stage 3: Code Generation
            await self.stage_3_code_generation()
            
            # Stage 4: Review & Test
            await self.stage_4_review_and_test()
            
            # Stage 5: Deployment
            await self.stage_5_deployment()
            
            # Mark as completed
            self.context.current_stage = "completed"
            self.save_context()
            
            # Final RAG index save
            self.rag_manager.scan_project_files()
            self.rag_manager.save_rag_index()
            
            logger.info(f"✅ Workflow completed successfully!")
            logger.info(f"📁 Project files saved in: {self.project_dir}")
            
            return self.context
            
        except Exception as e:
            logger.error(f"❌ Workflow failed: {e}")
            # Save current progress
            self.save_context()
            raise