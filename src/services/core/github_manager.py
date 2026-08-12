import os
from github import Github
import logging
logger = logging.getLogger(__name__)


class GitHubManager:
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        if not self.token:
            raise ValueError("GITHUB_TOKEN environment variable is required")
        self.repo_name = "baxtiyorjongaziyev/oisha-os"
        self.gh = Github(self.token)
        self.repo = self.gh.get_repo(self.repo_name)

    def push(self, path, content, message):
        try:
            old = self.repo.get_contents(path)
            self.repo.update_file(path, message, content, old.sha)
        except Exception:
            logger.error("Exception handled in %s", __name__, exc_info=True)
            self.repo.create_file(path, message, content)
        return True


github_manager = GitHubManager()
