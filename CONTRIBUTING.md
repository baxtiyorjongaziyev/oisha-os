# Contributing to Oisha-OS

Thank you for your interest in contributing to **Oisha-OS**! We follow a "Surgical Management" philosophy where AI and Humans collaborate to maintain a high-performance CRM environment.

## 🚀 Getting Started

1. **Fork the Repository**: Create your own fork of the `oisha-os` repo.
2. **Clone Locally**: 
   ```bash
   git clone https://github.com/your-username/oisha-os.git
   cd oisha-os
   ```
3. **Setup Environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env
   ```
   *Fill in your .env with valid credentials.*

## 🛠 Development Guidelines

### Code Style
- We use **Black** for Python formatting.
- We use **Ruff** for linting.
- Follow **Google-style docstrings**.

### Branching Strategy
- `main`: Production-ready code.
- `dev`: Active development and integration.
- `feature/*`: New features.
- `bugfix/*`: Bug fixes.

### Commit Messages
We follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat: ...` for new features.
- `fix: ...` for bug fixes.
- `docs: ...` for documentation changes.
- `refactor: ...` for code refactoring.

## 🧪 Testing

Before submitting a Pull Request, ensure that all tests pass:
```bash
pytest tests/
```

## 📬 Submitting a Pull Request

1. Create a branch for your changes.
2. Commit your changes with descriptive messages.
3. Push to your fork.
4. Open a Pull Request against the `dev` branch (or `main` if authorized).
5. Ensure the CI pipeline passes.

## 🤖 AI-Agent Interaction

Oisha-OS is designed to be managed by AI agents. If you are an AI assistant working on this repo:
1. Always check `CLAUDE.md` for context.
2. Document your changes in `CHANGELOG.md` or a `walkthrough.md`.
3. Prioritize system stability and security.

---

*Together, we build the future of autonomous business operations.*
