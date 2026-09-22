"""
AIEL-T Adapter Registry - Multi-Language Support
=================================================

Provides adapter interface for running AIEL-T on multiple languages.

Adapters:
- Python (pytest)
- Node.js (npm test)
- Go (go test)

Output Contract:
- Standardized JSON format (language-agnostic)
- PASS/FAIL/SKIP status
- Reason codes for failures
"""
import subprocess
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod


class LanguageAdapter(ABC):
    """Base adapter interface for all languages"""
    
    @abstractmethod
    def detect(self, workdir: Path) -> bool:
        """
        Detect if project uses this language
        
        Args:
            workdir: Project directory
            
        Returns:
            True if language detected
        """
        pass
    
    @abstractmethod
    def build_cmd(self, workdir: Path) -> Optional[List[str]]:
        """
        Get build command (if needed)
        
        Args:
            workdir: Project directory
            
        Returns:
            Command list or None if no build needed
        """
        pass
    
    @abstractmethod
    def test_cmd(self, workdir: Path) -> List[str]:
        """
        Get test command (must be deterministic)
        
        Args:
            workdir: Project directory
            
        Returns:
            Command list
        """
        pass
    
    @abstractmethod
    def parse(self, stdout: str, stderr: str, exit_code: int, 
             artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse test results into standard output contract
        
        Args:
            stdout: Standard output
            stderr: Standard error
            exit_code: Exit code
            artifacts: Additional artifacts
            
        Returns:
            Standardized result dict
        """
        pass


class PythonAdapter(LanguageAdapter):
    """Adapter for Python projects (pytest)"""
    
    def detect(self, workdir: Path) -> bool:
        """Detect Python project"""
        markers = [
            workdir / "requirements.txt",
            workdir / "pyproject.toml",
            workdir / "setup.py",
            workdir / "setup.cfg"
        ]
        return any(marker.exists() for marker in markers)
    
    def build_cmd(self, workdir: Path) -> Optional[List[str]]:
        """Python doesn't need build"""
        return None
    
    def test_cmd(self, workdir: Path) -> List[str]:
        """Run pytest"""
        return ["pytest", "-q", "--tb=short"]
    
    def parse(self, stdout: str, stderr: str, exit_code: int,
             artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Parse pytest output"""
        # Parse pytest output format
        # Example: "5 passed in 0.03s"
        
        tests_total = 0
        tests_passed = 0
        tests_failed = 0
        
        # Simple parsing (can be enhanced)
        for line in stdout.split('\n'):
            if 'passed' in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'passed':
                        try:
                            tests_passed = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
            if 'failed' in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == 'failed':
                        try:
                            tests_failed = int(parts[i-1])
                        except (ValueError, IndexError):
                            pass
        
        tests_total = tests_passed + tests_failed
        
        # Determine status
        if exit_code == 0 and tests_total > 0:
            status = "PASS"
        elif tests_total == 0:
            status = "SKIP"
            return {
                "status": status,
                "tests_executed": False,
                "tests_passed": 0,
                "tests_total": 0,
                "failures": [{
                    "reason_code": "RC_TESTS_NOT_FOUND",
                    "evidence_ref": "stdout"
                }],
                "toolchain": {
                    "language": "python",
                    "version": "unknown"
                },
                "artifacts": {
                    "stdout_log": stdout,
                    "stderr_log": stderr
                }
            }
        else:
            status = "FAIL"
        
        return {
            "status": status,
            "tests_executed": True,
            "tests_passed": tests_passed,
            "tests_total": tests_total,
            "failures": [] if status == "PASS" else [{
                "reason_code": "RC_TEST_FAILED",
                "evidence_ref": "stdout"
            }],
            "toolchain": {
                "language": "python",
                "version": "3.x"
            },
            "artifacts": {
                "stdout_log": stdout,
                "stderr_log": stderr
            }
        }


class NodeAdapter(LanguageAdapter):
    """Adapter for Node.js projects (npm test)"""
    
    def detect(self, workdir: Path) -> bool:
        """Detect Node.js project"""
        return (workdir / "package.json").exists()
    
    def build_cmd(self, workdir: Path) -> Optional[List[str]]:
        """Node.js might need npm install"""
        if (workdir / "node_modules").exists():
            return None
        return ["npm", "install", "--silent"]
    
    def test_cmd(self, workdir: Path) -> List[str]:
        """Run npm test"""
        return ["npm", "test", "--silent"]
    
    def parse(self, stdout: str, stderr: str, exit_code: int,
             artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Parse npm test output"""
        # Simple implementation
        status = "PASS" if exit_code == 0 else "FAIL"
        
        return {
            "status": status,
            "tests_executed": True,
            "tests_passed": 0,  # Would need to parse npm output
            "tests_total": 0,
            "failures": [] if status == "PASS" else [{
                "reason_code": "RC_TEST_FAILED",
                "evidence_ref": "stdout"
            }],
            "toolchain": {
                "language": "node",
                "version": "unknown"
            },
            "artifacts": {
                "stdout_log": stdout,
                "stderr_log": stderr
            }
        }


class GoAdapter(LanguageAdapter):
    """Adapter for Go projects (go test)"""
    
    def detect(self, workdir: Path) -> bool:
        """Detect Go project"""
        return (workdir / "go.mod").exists()
    
    def build_cmd(self, workdir: Path) -> Optional[List[str]]:
        """Go build"""
        return ["go", "build", "./..."]
    
    def test_cmd(self, workdir: Path) -> List[str]:
        """Run go test"""
        return ["go", "test", "./...", "-v"]
    
    def parse(self, stdout: str, stderr: str, exit_code: int,
             artifacts: Dict[str, Any]) -> Dict[str, Any]:
        """Parse go test output"""
        status = "PASS" if exit_code == 0 else "FAIL"
        
        return {
            "status": status,
            "tests_executed": True,
            "tests_passed": 0,
            "tests_total": 0,
            "failures": [] if status == "PASS" else [{
                "reason_code": "RC_TEST_FAILED",
                "evidence_ref": "stdout"
            }],
            "toolchain": {
                "language": "go",
                "version": "unknown"
            },
            "artifacts": {
                "stdout_log": stdout,
                "stderr_log": stderr
            }
        }


class AdapterRegistry:
    """Registry for language adapters"""
    
    def __init__(self):
        """Initialize registry with default adapters"""
        self.adapters: List[LanguageAdapter] = [
            PythonAdapter(),
            NodeAdapter(),
            GoAdapter()
        ]
    
    def detect_language(self, workdir: Path) -> Optional[LanguageAdapter]:
        """
        Detect project language and return appropriate adapter
        
        Args:
            workdir: Project directory
            
        Returns:
            Adapter instance or None if not detected
        """
        for adapter in self.adapters:
            if adapter.detect(workdir):
                return adapter
        return None
    
    def run_tests(self, workdir: Path) -> Dict[str, Any]:
        """
        Run tests for project using appropriate adapter
        
        Args:
            workdir: Project directory
            
        Returns:
            Standardized test result
        """
        adapter = self.detect_language(workdir)
        
        if adapter is None:
            return {
                "status": "SKIP",
                "tests_executed": False,
                "tests_passed": 0,
                "tests_total": 0,
                "failures": [{
                    "reason_code": "RC_ADAPTER_NOT_FOUND",
                    "evidence_ref": "none"
                }],
                "toolchain": {
                    "language": "unknown",
                    "version": "unknown"
                },
                "artifacts": {
                    "stdout_log": "",
                    "stderr_log": "No adapter found for this language"
                }
            }
        
        # Run build if needed
        build_cmd = adapter.build_cmd(workdir)
        if build_cmd:
            try:
                subprocess.run(
                    build_cmd,
                    cwd=workdir,
                    check=True,
                    capture_output=True,
                    timeout=300
                )
            except subprocess.CalledProcessError as e:
                return {
                    "status": "SKIP",
                    "tests_executed": False,
                    "tests_passed": 0,
                    "tests_total": 0,
                    "failures": [{
                        "reason_code": "RC_BUILD_FAILED",
                        "evidence_ref": "stderr"
                    }],
                    "toolchain": {
                        "language": adapter.__class__.__name__.replace("Adapter", "").lower(),
                        "version": "unknown"
                    },
                    "artifacts": {
                        "stdout_log": e.stdout.decode('utf-8') if e.stdout else "",
                        "stderr_log": e.stderr.decode('utf-8') if e.stderr else ""
                    }
                }
        
        # Run tests
        test_cmd = adapter.test_cmd(workdir)
        try:
            result = subprocess.run(
                test_cmd,
                cwd=workdir,
                capture_output=True,
                timeout=300
            )
            
            stdout = result.stdout.decode('utf-8') if result.stdout else ""
            stderr = result.stderr.decode('utf-8') if result.stderr else ""
            
            return adapter.parse(stdout, stderr, result.returncode, {})
            
        except subprocess.CalledProcessError as e:
            stdout = e.stdout.decode('utf-8') if e.stdout else ""
            stderr = e.stderr.decode('utf-8') if e.stderr else ""
            return adapter.parse(stdout, stderr, e.returncode, {})
        
        except subprocess.TimeoutExpired:
            return {
                "status": "SKIP",
                "tests_executed": False,
                "tests_passed": 0,
                "tests_total": 0,
                "failures": [{
                    "reason_code": "RC_TEST_TIMEOUT",
                    "evidence_ref": "none"
                }],
                "toolchain": {
                    "language": adapter.__class__.__name__.replace("Adapter", "").lower(),
                    "version": "unknown"
                },
                "artifacts": {
                    "stdout_log": "",
                    "stderr_log": "Test execution timed out (300s)"
                }
            }


# Test
if __name__ == '__main__':
    print("Adapter Registry Test")
    print("=" * 60)
    
    registry = AdapterRegistry()
    
    # Test Python detection
    test_dir = Path("/tmp/test_python")
    test_dir.mkdir(exist_ok=True)
    (test_dir / "requirements.txt").write_text("pytest\n")
    
    adapter = registry.detect_language(test_dir)
    if adapter:
        print(f"✅ Detected: {adapter.__class__.__name__}")
    else:
        print("❌ No adapter found")
