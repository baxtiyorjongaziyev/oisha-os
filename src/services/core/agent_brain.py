from src.services.core.github_manager import github_manager


class OishaBrain:
    async def evolve(self, task):
        # Kelajakda bu yerda Gemini kod yozadi
        new_content = f"# Autonomous Update\n# Task: {task}\nimport os"
        github_manager.push(
            "src/services/core/last_fix.py", new_content, f"Agentic fix: {task}"
        )
        return True


oisha_brain = OishaBrain()
