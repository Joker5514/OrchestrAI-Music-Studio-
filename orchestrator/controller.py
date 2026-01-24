#!/usr/bin/env python3
"""
OrchestrAI Controller
Multi-agent orchestrator for 7-day AI DAW build
Manages task delegation, API calls, and GitHub integration
"""

import os
import json
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Any
import subprocess
import yaml

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")

class OrchestrAI:
    """
    Multi-agent orchestrator for DAW AI build system.
    Delegates tasks to appropriate AI models based on LM Arena rankings.
    """

    def __init__(self, config_path: str = CONFIG_PATH):
        self.config_path = config_path
        self.load_config()
        self.build_log = []
        self.timestamp = datetime.now().isoformat()

    def load_config(self):
        """Load orchestrator configuration."""
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        except FileNotFoundError:
            print(f"[ERROR] Config not found: {self.config_path}")
            print("[ACTION] Run: cp orchestrator/config.example.yaml orchestrator/config.yaml")
            sys.exit(1)

    def delegate(self, day: int, task: str, ai_model: str, prompt_key: str, 
                 output_file: str, dependencies: List[str] = None) -> Dict[str, Any]:
        """
        Delegate a task to an AI model.
        
        Args:
            day: Build day (1-7)
            task: Task description
            ai_model: Model name ("claude-opus", "gemini-3-pro", etc.)
            prompt_key: Key to prompt template
            output_file: Output file path
            dependencies: List of required input files
        
        Returns:
            Result dict with status, output, cost, duration
        """
        print(f"\n[DAY {day}] Delegating: {task}")
        print(f"  Model: {ai_model}")
        print(f"  Output: {output_file}")

        # Check dependencies
        if dependencies:
            for dep in dependencies:
                if not os.path.exists(dep):
                    print(f"[ERROR] Missing dependency: {dep}")
                    return {"status": "failed", "reason": f"Missing dependency: {dep}"}

        # Get API client for model
        api_client = self.get_api_client(ai_model)
        if not api_client:
            return {"status": "failed", "reason": f"No API key for {ai_model}"}

        # Load prompt
        prompt = self.load_prompt(prompt_key)
        if not prompt:
            return {"status": "failed", "reason": f"Prompt not found: {prompt_key}"}

        # Call API
        result = api_client.generate(prompt)
        if not result["success"]:
            return {"status": "failed", "reason": result.get("error", "API error")}

        # Write output
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w') as f:
            f.write(result["content"])

        print(f"  ✅ Output: {output_file}")
        print(f"  Cost: ${result.get('cost', 0):.4f}")
        print(f"  Duration: {result.get('duration', 0):.1f}s")

        # Log to build history
        self.build_log.append({
            "day": day,
            "task": task,
            "model": ai_model,
            "output": output_file,
            "cost": result.get("cost", 0),
            "status": "completed",
            "timestamp": datetime.now().isoformat()
        })

        return {"status": "completed", "output_file": output_file, **result}

    def get_api_client(self, model: str):
        """Get API client for specified model."""
        model_config = self.config.get("models", {}).get(model, {})
        api_key = os.getenv(model_config.get("env_key"), model_config.get("api_key"))
        
        if not api_key:
            return None

        # Return appropriate client wrapper
        if "claude" in model:
            return ClaudeClient(api_key, model)
        elif "gemini" in model:
            return GeminiClient(api_key, model)
        elif "deepseek" in model:
            return DeepSeekClient(api_key, model)
        elif "gpt" in model:
            return GPTClient(api_key, model)
        else:
            return None

    def load_prompt(self, prompt_key: str) -> str:
        """Load prompt template by key."""
        prompt_file = os.path.join(os.path.dirname(__file__), "prompts", f"{prompt_key}.txt")
        try:
            with open(prompt_file, 'r') as f:
                return f.read()
        except FileNotFoundError:
            return None

    def git_commit_output(self, file_path: str, message: str) -> bool:
        """Auto-commit generated file to GitHub."""
        try:
            subprocess.run(["git", "add", file_path], check=True, cwd=os.getcwd())
            subprocess.run(["git", "commit", "-m", message], check=True, cwd=os.getcwd())
            print(f"  📝 Committed: {file_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"  [WARNING] Git commit failed: {e}")
            return False

    def save_build_log(self):
        """Save build execution log."""
        log_file = f"orchestrator/logs/build_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, 'w') as f:
            json.dump(self.build_log, f, indent=2)
        print(f"\n📊 Build log saved: {log_file}")

    def run_day(self, day: int):
        """Execute all tasks for a specific build day."""
        print(f"\n" + "="*60)
        print(f"DAY {day} - {self.timestamp}")
        print("="*60)

        # Define build phases
        phases = {
            1: [
                {"task": "System Architecture Design", "model": "gemini-3-pro", 
                 "prompt": "1.1_architecture", "output": "docs/ARCHITECTURE.md"}
            ],
            2: [
                {"task": "Audio Engine Core", "model": "claude-opus", 
                 "prompt": "2.1_audio_engine", "output": "backend/core/audio_engine.py",
                 "deps": ["docs/ARCHITECTURE.md"]},
            ],
            3: [
                {"task": "Voice Service & Mastering", "model": "claude-opus", 
                 "prompt": "2.2_voice_mastering", "output": "backend/core/voice_service.py",
                 "deps": ["backend/core/audio_engine.py"]},
            ],
            4: [
                {"task": "Timeline React Component", "model": "claude-sonnet", 
                 "prompt": "3.1_timeline", "output": "frontend/components/Timeline.tsx"},
                {"task": "Mixer React Component", "model": "claude-sonnet", 
                 "prompt": "3.2_mixer", "output": "frontend/components/Mixer.tsx"},
            ],
            5: [
                {"task": "AI Assistant Panel", "model": "claude-opus", 
                 "prompt": "3.3_assistant_panel", "output": "frontend/components/AIAssistant.tsx"},
            ],
            6: [
                {"task": "DSP Algorithms & Filters", "model": "deepseek", 
                 "prompt": "4.1_dsp_algorithms", "output": "dsp/algorithms.py"},
            ],
            7: [
                {"task": "Docker & Deployment", "model": "gpt-5-high", 
                 "prompt": "5.1_deployment", "output": "deployment/Dockerfile"},
            ]
        }

        if day not in phases:
            print(f"[ERROR] Invalid day: {day}. Valid days: 1-7")
            return

        total_cost = 0
        for phase in phases[day]:
            result = self.delegate(
                day=day,
                task=phase["task"],
                ai_model=phase["model"],
                prompt_key=phase["prompt"],
                output_file=phase["output"],
                dependencies=phase.get("deps")
            )
            if result["status"] == "completed":
                total_cost += result.get("cost", 0)
                # Auto-commit
                self.git_commit_output(
                    phase["output"],
                    f"[DAY {day}] Auto-generated: {phase['task']}"
                )

        print(f"\n💰 Day {day} total cost: ${total_cost:.2f}")
        self.save_build_log()


# API Client Wrappers (Stubs - implement with actual API calls)
class ClaudeClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> Dict[str, Any]:
        # Implement Anthropic API call
        print(f"  [STUB] Calling Claude API ({self.model})...")
        return {"success": True, "content": "", "cost": 0.05, "duration": 2.3}

class GeminiClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> Dict[str, Any]:
        # Implement Google Gemini API call
        print(f"  [STUB] Calling Gemini API ({self.model})...")
        return {"success": True, "content": "", "cost": 0.03, "duration": 1.8}

class DeepSeekClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> Dict[str, Any]:
        # Implement DeepSeek API call
        print(f"  [STUB] Calling DeepSeek API ({self.model})...")
        return {"success": True, "content": "", "cost": 0.016, "duration": 2.1}

class GPTClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str) -> Dict[str, Any]:
        # Implement OpenAI API call
        print(f"  [STUB] Calling GPT API ({self.model})...")
        return {"success": True, "content": "", "cost": 0.04, "duration": 2.5}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OrchestrAI DAW Build Controller")
    parser.add_argument("--day", type=int, choices=range(1, 8), help="Build day (1-7)")
    parser.add_argument("--trigger", action="store_true", help="Trigger build execution")
    parser.add_argument("--status", action="store_true", help="Show build status")

    args = parser.parse_args()

    orchestrator = OrchestrAI()

    if args.trigger and args.day:
        orchestrator.run_day(args.day)
    elif args.status:
        print("[TODO] Implement status command")
    else:
        parser.print_help()
