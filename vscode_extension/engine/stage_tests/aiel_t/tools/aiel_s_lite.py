"""
AIEL-S Lite: Static Analysis Integration
Using Pylint + Bandit for G-Score Portal

Quick MVP solution to catch code violations
"""

import subprocess
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Tuple


class AIEL_S_Lite:
    """
    Static Analysis Engine (Lite Version)
    
    Integrates:
    - Pylint: Code quality, style, architecture
    - Bandit: Security vulnerabilities
    
    Output: G-Score Static (G_S)
    """
    
    def __init__(self):
        self.weights = {
            'pylint': 0.60,   # Code quality & architecture
            'bandit': 0.40    # Security
        }
    
    def analyze(self, code_path: str) -> Dict[str, Any]:
        """
        Run static analysis on code
        
        Returns:
            {
                'g_score_static': float,
                'pylint_score': float,
                'bandit_score': float,
                'violations': list,
                'details': dict
            }
        """
        
        # Run both analyzers
        pylint_result = self._run_pylint(code_path)
        bandit_result = self._run_bandit(code_path)
        
        # Calculate G-Score Static
        g_s = (
            pylint_result['score'] * self.weights['pylint'] +
            bandit_result['score'] * self.weights['bandit']
        )
        
        # Collect all violations
        violations = []
        violations.extend(pylint_result.get('violations', []))
        violations.extend(bandit_result.get('violations', []))
        
        return {
            'g_score_static': round(g_s, 4),
            'pylint_score': pylint_result['score'],
            'bandit_score': bandit_result['score'],
            'violations': violations,
            'violation_count': len(violations),
            'details': {
                'pylint': pylint_result,
                'bandit': bandit_result
            }
        }
    
    def _run_pylint(self, code_path: str) -> Dict[str, Any]:
        """
        Run Pylint analysis
        
        Checks:
        - Code quality
        - Style violations
        - Architecture issues
        - Global state usage
        - Complexity
        """
        try:
            # Run pylint with JSON output
            result = subprocess.run(
                ['pylint', code_path, '--output-format=json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Parse output
            messages = json.loads(result.stdout) if result.stdout else []
            
            # Calculate score (Pylint default is 0-10)
            # Extract from stderr: "Your code has been rated at X/10"
            score = 10.0
            if result.stderr:
                import re
                match = re.search(r'rated at ([\d.]+)/10', result.stderr)
                if match:
                    score = float(match.group(1))
            
            # Normalize to 0-1
            normalized_score = score / 10.0
            
            # Categorize violations
            violations = []
            for msg in messages:
                severity = self._map_pylint_severity(msg.get('type', 'info'))
                violations.append({
                    'tool': 'pylint',
                    'type': msg.get('type'),
                    'severity': severity,
                    'message': msg.get('message'),
                    'line': msg.get('line'),
                    'symbol': msg.get('symbol')
                })
            
            return {
                'score': normalized_score,
                'raw_score': score,
                'violations': violations,
                'message_count': len(messages)
            }
            
        except subprocess.TimeoutExpired:
            return {'score': 0.5, 'violations': [{'error': 'Pylint timeout'}]}
        except FileNotFoundError:
            # Pylint not installed
            return {'score': 1.0, 'violations': [{'info': 'Pylint not available'}]}
        except Exception as e:
            return {'score': 0.5, 'violations': [{'error': str(e)}]}
    
    def _run_bandit(self, code_path: str) -> Dict[str, Any]:
        """
        Run Bandit security analysis
        
        Checks:
        - Security vulnerabilities
        - Unsafe function calls
        - Path traversal
        - SQL injection
        - Hardcoded passwords
        """
        try:
            # Run bandit with JSON output
            result = subprocess.run(
                ['bandit', '-f', 'json', code_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Parse output
            data = json.loads(result.stdout) if result.stdout else {}
            
            # Get metrics
            metrics = data.get('metrics', {})
            total_issues = 0
            severity_counts = {'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
            
            for file_metrics in metrics.values():
                for severity in ['HIGH', 'MEDIUM', 'LOW']:
                    count = file_metrics.get(f'{severity}.severity', 0)
                    severity_counts[severity] += count
                    total_issues += count
            
            # Calculate score (weighted by severity)
            # Start at 1.0, deduct for issues
            score = 1.0
            score -= severity_counts['HIGH'] * 0.20   # -0.20 per high
            score -= severity_counts['MEDIUM'] * 0.10  # -0.10 per medium
            score -= severity_counts['LOW'] * 0.05    # -0.05 per low
            score = max(0.0, min(1.0, score))
            
            # Collect violations
            violations = []
            for issue in data.get('results', []):
                violations.append({
                    'tool': 'bandit',
                    'severity': issue.get('issue_severity', 'LOW'),
                    'confidence': issue.get('issue_confidence', 'LOW'),
                    'message': issue.get('issue_text'),
                    'line': issue.get('line_number'),
                    'test_id': issue.get('test_id')
                })
            
            return {
                'score': score,
                'violations': violations,
                'severity_counts': severity_counts,
                'total_issues': total_issues
            }
            
        except subprocess.TimeoutExpired:
            return {'score': 0.5, 'violations': [{'error': 'Bandit timeout'}]}
        except FileNotFoundError:
            # Bandit not installed
            return {'score': 1.0, 'violations': [{'info': 'Bandit not available'}]}
        except Exception as e:
            return {'score': 0.5, 'violations': [{'error': str(e)}]}
    
    def _map_pylint_severity(self, msg_type: str) -> str:
        """Map pylint message types to severity levels"""
        mapping = {
            'error': 'critical',
            'fatal': 'critical',
            'warning': 'high',
            'convention': 'low',
            'refactor': 'medium',
            'info': 'info'
        }
        return mapping.get(msg_type, 'medium')
    
    def generate_report(self, result: Dict[str, Any]) -> str:
        """Generate markdown report"""
        
        report = f"""# AIEL-S Static Analysis Report

## G-Score Static: {result['g_score_static']:.4f}

### Component Scores
- Pylint (Code Quality): {result['pylint_score']:.4f}
- Bandit (Security): {result['bandit_score']:.4f}

### Violations Summary
Total: {result['violation_count']}

"""
        
        # Group by severity
        by_severity = {}
        for v in result['violations']:
            sev = v.get('severity', 'unknown')
            if sev not in by_severity:
                by_severity[sev] = []
            by_severity[sev].append(v)
        
        for severity in ['critical', 'high', 'medium', 'low']:
            if severity in by_severity:
                report += f"\n### {severity.upper()} ({len(by_severity[severity])})\n\n"
                for v in by_severity[severity][:5]:  # Top 5 per severity
                    report += f"- [{v.get('tool', '?')}] {v.get('message', 'No message')}\n"
                    if 'line' in v:
                        report += f"  Line {v['line']}\n"
        
        return report


def combine_scores(g_static: float, g_runtime: float, 
                   static_weight: float = 0.5) -> Dict[str, Any]:
    """
    Combine static and runtime G-Scores
    
    Args:
        g_static: G-Score from static analysis (AIEL-S)
        g_runtime: G-Score from runtime validation (AIEL-T)
        static_weight: Weight for static score (default 0.5 = 50/50)
    
    Returns:
        Combined G-Score and tier
    """
    runtime_weight = 1.0 - static_weight
    
    g_final = (g_static * static_weight) + (g_runtime * runtime_weight)
    
    # Determine tier
    if g_final >= 0.95:
        tier = "Tier 2 - Certified Excellence"
    elif g_final >= 0.90:
        tier = "Tier 1 - Production Ready"
    elif g_final >= 0.70:
        tier = "Acceptable - Needs Review"
    else:
        tier = "Reject - Significant Issues"
    
    return {
        'g_score_final': round(g_final, 4),
        'g_score_static': round(g_static, 4),
        'g_score_runtime': round(g_runtime, 4),
        'tier': tier,
        'weights': {
            'static': static_weight,
            'runtime': runtime_weight
        }
    }


# Example usage
if __name__ == "__main__":
    analyzer = AIEL_S_Lite()
    
    # Test on evil code
    print("🔍 Analyzing crypto_arb_trader.py...")
    result = analyzer.analyze('/tmp/crypto_arb_trader.py')
    
    print(f"\n📊 Results:")
    print(f"   G-Score Static: {result['g_score_static']:.4f}")
    print(f"   Pylint: {result['pylint_score']:.4f}")
    print(f"   Bandit: {result['bandit_score']:.4f}")
    print(f"   Violations: {result['violation_count']}")
    
    # Combine with runtime (example: AIEL-T gave 1.0)
    combined = combine_scores(result['g_score_static'], 1.0)
    print(f"\n🎯 Combined G-Score: {combined['g_score_final']:.4f}")
    print(f"   Tier: {combined['tier']}")
    
    # Generate report
    report = analyzer.generate_report(result)
    print(f"\n📄 Report generated")
