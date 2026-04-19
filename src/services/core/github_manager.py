import os
from github import Github

class GitHubManager:
    def __init__(self):
        # Tokenni env dan olamiz, bo'lmasa default
        self.token = os.getenv("GITHUB_TOKEN", "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")
        self.repo_name = "baxtiyorjongaziyev/oisha-os"
        self.gh = Github(self.token)
        self.repo = self.gh.get_repo(self.repo_name)

    def push(self, path, content, message):
        try:
            try:
                old = self.repo.get_contents(path)
                self.repo.update_file(path, message, content, old.sha)
            except:
                self.repo.create_file(path, message, content)
            return True
        except Exception as e:
            return False

github_manager = GitHubManager()
