# Contributing to Yak Similarity Analyzer

Thank you for your interest in contributing to the Yak Similarity Analyzer project!

## Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/yak-similarity-analyzer.git
   cd yak-similarity-analyzer
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

4. **Run tests:**
   ```bash
   pytest tests/ -v
   ```

## Code Style

- Follow PEP 8 guidelines
- Use meaningful variable names
- Add docstrings for functions and classes
- Keep functions focused and small

## Security Guidelines

- Never commit secrets or keys
- Follow secure coding practices
- Test authorization mechanisms thoroughly
- Report security vulnerabilities privately

## Testing

- Write tests for new features
- Ensure all tests pass before submitting
- Test both positive and negative cases
- Test authorization and tamper protection

## Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Reporting Issues

Please use the GitHub issue tracker to report bugs or request features.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.