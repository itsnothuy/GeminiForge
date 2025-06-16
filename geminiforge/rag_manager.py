from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

class RAGManager:
    """Manage the RAG system so Gemini can review the source code"""
    
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.source_index = {}
        self.file_contents = {}
        
    def scan_project_files(self) -> Dict[str, Any]:
        """Scan the entire project to build an index for RAG system"""
        logger.info("🔍 Scanning project files for RAG system...")
        
        file_types = {
            ".py": "python",
            ".js": "javascript", 
            ".java": "java",
            ".sql": "sql",
            ".json": "json",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".md": "markdown",
            ".txt": "text",
            ".properties": "properties"
        }
        
        project_structure = {
            "files": {},
            "directories": [],
            "modules": {},
            "summary": {
                "total_files": 0,
                "file_types": {},
                "last_scan": datetime.now().isoformat()
            }
        }
        
        if not self.project_dir.exists():
            return project_structure
            
        for file_path in self.project_dir.rglob("*"):
            if file_path.is_file():
                try:
                    relative_path = file_path.relative_to(self.project_dir)
                    file_ext = file_path.suffix.lower()
                    file_type = file_types.get(file_ext, "unknown")
                    
                    # Read file content (limit size to avoid overload)
                    file_size = file_path.stat().st_size
                    if file_size < 50000:  # < 50KB
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                        except:
                            with open(file_path, 'r', encoding='latin-1') as f:
                                content = f.read()
                    else:
                        content = f"[File too large: {file_size} bytes]"
                    
                    project_structure["files"][str(relative_path)] = {
                        "type": file_type,
                        "size": file_size,
                        "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                        "content_preview": content[:500] if len(content) > 500 else content
                    }
                    
                    # Full content for small files 
                    if file_size < 10000:  # < 10KB
                        self.file_contents[str(relative_path)] = content
                    
                    # Update statistics
                    project_structure["summary"]["total_files"] += 1
                    project_structure["summary"]["file_types"][file_type] = \
                        project_structure["summary"]["file_types"].get(file_type, 0) + 1
                        
                except Exception as e:
                    logger.warning(f"⚠️ Could not process file {file_path}: {e}")
            
            elif file_path.is_dir():
                relative_path = file_path.relative_to(self.project_dir)
                if relative_path != Path("."):
                    project_structure["directories"].append(str(relative_path))
        
        # Organize by modules
        for file_path in project_structure["files"]:
            parts = Path(file_path).parts
            if len(parts) > 1:
                module_name = parts[1] if parts[0] == "03_code" else parts[0]
                if module_name not in project_structure["modules"]:
                    project_structure["modules"][module_name] = []
                project_structure["modules"][module_name].append(file_path)
        
        self.source_index = project_structure
        logger.info(f"✅ Scanned {project_structure['summary']['total_files']} files")
        return project_structure
    
    def get_context_for_stage(self, stage: str) -> str:
        """Get the appropriate context for each stage"""
        if not self.source_index:
            self.scan_project_files()
        
        context_builders = {
            "requirements": self._build_requirements_context,
            "architecture": self._build_architecture_context,
            "code": self._build_code_context,
            "review": self._build_review_context,
            "deployment": self._build_deployment_context
        }
        
        builder = context_builders.get(stage, self._build_general_context)
        return builder()
    
    def _build_requirements_context(self) -> str:
        """Context for requirements stage"""
        req_files = [f for f in self.source_index.get("files", {}) 
                    if "01_requirements" in f or "requirements" in f.lower()]
        
        context = "EXISTING REQUIREMENTS FILES:\n"
        for file_path in req_files:
            if file_path in self.file_contents:
                context += f"\n{file_path}:\n{self.file_contents[file_path]}\n"
        
        return context
    
    def _build_architecture_context(self) -> str:
        """Context for architecture stage"""
        arch_files = [f for f in self.source_index.get("files", {}) 
                     if "02_architecture" in f or "architecture" in f.lower()]
        req_files = [f for f in self.source_index.get("files", {}) 
                    if "01_requirements" in f]
        
        context = "EXISTING ARCHITECTURE & REQUIREMENTS:\n"
        
        # Add requirements context
        for file_path in req_files:
            if file_path in self.file_contents:
                context += f"\nREQUIREMENTS - {file_path}:\n{self.file_contents[file_path]}\n"
        
        # Add architecture context  
        for file_path in arch_files:
            if file_path in self.file_contents:
                context += f"\nARCHITECTURE - {file_path}:\n{self.file_contents[file_path]}\n"
        
        return context
    
    def _build_code_context(self) -> str:
        """Context for code generation stage"""
        relevant_files = []
        
        # Requirements and Architecture
        for pattern in ["01_requirements", "02_architecture"]:
            relevant_files.extend([f for f in self.source_index.get("files", {}) if pattern in f])
        
        # Existing code files
        code_files = [f for f in self.source_index.get("files", {}) if "03_code" in f]
        
        context = "PROJECT CONTEXT FOR CODE GENERATION:\n\n"
        
        # Add previous stages
        for file_path in relevant_files:
            if file_path in self.file_contents:
                stage = "REQUIREMENTS" if "01_" in file_path else "ARCHITECTURE"
                context += f"{stage} - {file_path}:\n{self.file_contents[file_path]}\n\n"
        
        # Add existing code structure
        if code_files:
            context += "EXISTING CODE STRUCTURE:\n"
            modules = self.source_index.get("modules", {})
            for module_name, files in modules.items():
                if any("03_code" in f for f in files):
                    context += f"\nModule: {module_name}\n"
                    for file_path in files[:5]:  # Limit số files
                        if "03_code" in file_path and file_path in self.file_contents:
                            context += f"  {file_path}: {len(self.file_contents[file_path])} chars\n"
        
        return context
    
    def _build_review_context(self) -> str:
        """Context for review stage"""
        code_files = [f for f in self.source_index.get("files", {}) if "03_code" in f]
        
        context = "CODE FILES FOR REVIEW:\n\n"
        
        # Group by modules
        modules = self.source_index.get("modules", {})
        for module_name, files in modules.items():
            module_code_files = [f for f in files if "03_code" in f]
            if module_code_files:
                context += f"MODULE: {module_name}\n"
                for file_path in module_code_files[:10]:  # Limit files
                    file_info = self.source_index["files"].get(file_path, {})
                    context += f"  - {file_path} ({file_info.get('type', 'unknown')}, {file_info.get('size', 0)} bytes)\n"
                    
                    # Add preview for important files
                    if file_path in self.file_contents and any(ext in file_path for ext in ['.py', '.js', '.java']):
                        preview = self.file_contents[file_path][:300]
                        context += f"    Preview: {preview}...\n"
                context += "\n"
        
        return context
    
    def _build_deployment_context(self) -> str:
        """Context for deployment stage"""
        all_stages = ["01_requirements", "02_architecture", "03_code", "04_tests"]
        
        context = "COMPLETE PROJECT CONTEXT FOR DEPLOYMENT:\n\n"
        
        # Project summary
        summary = self.source_index.get("summary", {})
        context += f"Project Summary:\n"
        context += f"- Total files: {summary.get('total_files', 0)}\n"
        context += f"- File types: {summary.get('file_types', {})}\n"
        context += f"- Modules: {list(self.source_index.get('modules', {}).keys())}\n\n"
        
        # Key files from each stage
        for stage in all_stages:
            stage_files = [f for f in self.source_index.get("files", {}) if stage in f]
            if stage_files:
                stage_name = stage.split("_")[1].upper()
                context += f"{stage_name} FILES:\n"
                for file_path in stage_files[:3]:  # Top 3 files per stage
                    if file_path in self.file_contents:
                        context += f"  {file_path}:\n{self.file_contents[file_path][:200]}...\n\n"
        
        return context
    
    def _build_general_context(self) -> str:
        """General context"""
        return f"PROJECT STRUCTURE:\n{json.dumps(self.source_index, indent=2, ensure_ascii=False)}"
    
    def save_rag_index(self):
        """Save the RAG index to a file"""
        index_file = self.project_dir / "rag_index.json"
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(self.source_index, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Saved RAG index to {index_file}")