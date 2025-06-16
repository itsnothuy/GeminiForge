from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

from .api_manager import GeminiAPIManager
from .workflow import ProjectWorkflowManager

logger = logging.getLogger(__name__)

class WorkflowCLI:
    """Command Line Interface for workflow management"""
    
    def __init__(self, project_name: str):
        load_dotenv()
        
        self.API_KEYS = [
            os.getenv("GEMINI_API_KEY_1"),
            os.getenv("GEMINI_API_KEY_2"),
            os.getenv("GEMINI_API_KEY_3"),
            os.getenv("GEMINI_API_KEY_4"),
            os.getenv("GEMINI_API_KEY_5"),
        ]
        
        self.api_manager = GeminiAPIManager(self.API_KEYS)
        self.workflow = ProjectWorkflowManager(self.api_manager, project_name)
    
    async def status(self):
        """Show workflow status"""
        status = self.workflow.get_workflow_status()
        
        print(f"\n🔍 PROJECT STATUS: {self.workflow.project_name}")
        print(f"📍 Current Stage: {status['current_stage']}")
        print(f"📊 Progress: {status['progress']} ({status['percentage']:.1f}%)")
        print(f"📁 Project Directory: {status['project_dir']}")
        print(f"🕐 Last Updated: {status['last_updated']}")
        
        print(f"\n📋 STAGE COMPLETION:")
        for stage, completed in status['stages'].items():
            icon = "✅" if completed else "⏳"
            print(f"  {icon} {stage.capitalize()}")
        
        return status
    
    async def resume(self, user_input: str = None):
        """Resume workflow from current stage"""
        return await self.workflow.resume_workflow(user_input)
    
    async def run(self, user_input: str):
        """Run full workflow"""
        return await self.workflow.run_full_workflow(user_input)
    
    async def scan_files(self):
        """Scan and show project files"""
        index = self.workflow.rag_manager.scan_project_files()
        
        print(f"\n📂 PROJECT FILES SCAN:")
        print(f"📊 Total Files: {index['summary']['total_files']}")
        print(f"📁 Directories: {len(index['directories'])}")
        print(f"🔧 Modules: {len(index['modules'])}")
        
        print(f"\n📈 FILE TYPES:")
        for file_type, count in index['summary']['file_types'].items():
            print(f"  {file_type}: {count}")
        
        print(f"\n📦 MODULES:")
        for module, files in index['modules'].items():
            print(f"  {module}: {len(files)} files")
        
        return index

# Usage Example
async def main():
    """Example usage of the system with RAG and resume capability"""
    
    project_name = "ecommerce_platform"
    cli = WorkflowCLI(project_name)
    
    # Check current status
    await cli.status()
    
    # User Input for project requirements (Vietnamese)
    user_request_VN = """
    Tôi muốn xây dựng một nền tảng thương mại điện tử với các tính năng:
    - Quản lý sản phẩm và danh mục
    - Giỏ hàng và thanh toán
    - Quản lý đơn hàng
    - Hệ thống user và authentication
    - Admin dashboard
    - API cho mobile app
    - Tích hợp thanh toán VNPay, Momo
    - Hỗ trợ multi-language (Vietnamese, English)
    """

    # User Input for project requirements (English)
    user_request = """
    I want to build an e-commerce platform with features:
    - Product and category management
    - Shopping cart and checkout
    - Order management system
    - User system and authentication
    - Admin dashboard
    - Mobile app API
    - VNPay and Momo payment integration
    - Multi-language support (Vietnamese, English)
    """
    
    try:
        # Run or resume workflow
        if cli.workflow.context.current_stage == "not_started":
            print("🚀 Starting new workflow...")
            result = await cli.run(user_request)
        else:
            print("🔄 Resuming existing workflow...")
            result = await cli.resume(user_request)
        
        # Show final status
        await cli.status()
        
        # Scan final files
        await cli.scan_files()
        
        print("🎉 Project generation completed!")
        print(f"📁 Files saved in: {cli.workflow.project_dir}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💾 Progress has been saved. You can resume later.")
        await cli.status()

if __name__ == "__main__":
    asyncio.run(main())