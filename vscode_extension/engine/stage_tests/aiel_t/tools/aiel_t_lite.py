#!/usr/bin/env python3
"""
AIEL-T Lite - Quick Code Validator
Meta test: Validate G-Score Portal code!
"""

import ast
import re
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# SOVEREIGN SHIELD — Semantic Density Gate
# ---------------------------------------------------------------------------

def get_logical_loc(code: str) -> dict:
    """Count logical lines of code, excluding blank lines and comment-only lines.

    A "logical line" is any line whose stripped content is non-empty and does
    not start with ``#``.  The minimum threshold is 15 logical lines; modules
    below that are considered semantically hollow and flagged for hard-fail.

    Args:
        code: Raw source code string to analyse.

    Returns:
        dict with keys:
            - ``passed`` (bool): True if logical_loc >= 15.
            - ``logical_loc`` (int): Count of qualifying lines.
            - ``reason_code`` (str | None): ``"RC_SEMANTIC_DENSITY_LOW"`` on failure.
            - ``message`` (str): Human-readable verdict.
    """
    lines = code.splitlines()
    logical_lines = [
        ln for ln in lines
        if ln.strip() and not ln.strip().startswith("#")
    ]
    logical_loc: int = len(logical_lines)

    if logical_loc < 15:
        return {
            "passed": False,
            "logical_loc": logical_loc,
            "reason_code": "RC_SEMANTIC_DENSITY_LOW",
            "message": (
                f"Semantic density too low: {logical_loc} logical lines "
                f"(minimum: 15). Module may be a stub or hollow scaffold."
            ),
        }

    return {
        "passed": True,
        "logical_loc": logical_loc,
        "reason_code": None,
        "message": f"Semantic density OK: {logical_loc} logical lines.",
    }


# ---------------------------------------------------------------------------


class AIEL_T_Lite:
    """Quick AIEL-T implementation for testing"""
    
    def validate(self, code_path: str) -> dict:
        """Run validation and return G-Score"""
        
        with open(code_path) as f:
            code = f.read()
        
        # Run 4 engines
        inv_score = self._invariant_engine(code)
        pat_score = self._pattern_engine(code)
        con_score = self._contract_engine(code)
        sce_score = self._scenario_engine(code)
        
        # Calculate G-Score (weighted average)
        g_score = (
            inv_score * 0.30 +
            pat_score * 0.25 +
            con_score * 0.25 +
            sce_score * 0.20
        )
        
        # Determine tier
        if g_score >= 0.95:
            tier = "Tier 2 - Certified Excellence"
        elif g_score >= 0.90:
            tier = "Tier 1 - Production Ready"
        else:
            tier = "Needs Improvement"
        
        return {
            'file': Path(code_path).name,
            'g_score': round(g_score, 3),
            'tier': tier,
            'components': {
                'invariant': round(inv_score, 3),
                'pattern': round(pat_score, 3),
                'contract': round(con_score, 3),
                'scenario': round(sce_score, 3)
            },
            'issues': self._collect_issues(code)
        }
    
    def _invariant_engine(self, code: str) -> float:
        """Check invariants (INV_001-008)"""
        score = 1.0
        
        # INV_001: No division by zero
        if '/0' in code or '/ 0' in code:
            score -= 0.2
        
        # INV_002: Array bounds (check list access)
        if '[' in code and not 'try:' in code:
            score -= 0.1
        
        # INV_003: Type safety (has type hints?)
        if '->' in code or ': str' in code or ': int' in code:
            score += 0.1
        else:
            score -= 0.1
        
        # INV_004: Error handling
        if 'except' in code:
            score += 0.1
        else:
            score -= 0.15
        
        return max(0.0, min(1.0, score))
    
    def _pattern_engine(self, code: str) -> float:
        """Analyze code patterns"""
        score = 0.7  # Base score
        
        # Good patterns
        if 'class ' in code:
            score += 0.05  # OOP
        if 'def ' in code:
            score += 0.05  # Functions
        if 'import ' in code:
            score += 0.05  # Modularity
        if '"""' in code or "'''" in code:
            score += 0.1  # Documentation
        if 'typing' in code or 'Dict' in code or 'List' in code:
            score += 0.05  # Type hints
        
        # Bad patterns
        if 'global ' in code:
            score -= 0.1  # Global variables
        if code.count('print(') > 5:
            score -= 0.05  # Too many prints
        
        return max(0.0, min(1.0, score))
    
    def _contract_engine(self, code: str) -> float:
        """Check spec compliance"""
        score = 0.8  # Assume decent
        
        # Check structure
        try:
            tree = ast.parse(code)
            
            # Has functions/classes?
            has_func = any(isinstance(n, ast.FunctionDef) for n in ast.walk(tree))
            has_class = any(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
            
            if has_func:
                score += 0.1
            if has_class:
                score += 0.1
                
        except:
            score -= 0.3  # Syntax error!
        
        return max(0.0, min(1.0, score))
    
    def _scenario_engine(self, code: str) -> float:
        """Simulate behavior (simplified)"""
        score = 0.75
        
        # Check if runnable
        try:
            compile(code, '<string>', 'exec')
            score += 0.15  # Compiles!
        except:
            score -= 0.3  # Syntax error
        
        # Has main/entry point?
        if 'if __name__' in code or 'def main' in code:
            score += 0.1
        
        return max(0.0, min(1.0, score))
    
    def _collect_issues(self, code: str) -> list:
        """Collect issues found"""
        issues = []
        
        if 'except:' in code and 'except Exception:' not in code:
            issues.append({
                'type': 'bare_except',
                'severity': 'medium',
                'message': 'Bare except clause - should specify exception type'
            })
        
        if 'TODO' in code or 'FIXME' in code:
            issues.append({
                'type': 'todo',
                'severity': 'low',
                'message': 'TODO/FIXME comments found'
            })
        
        # Count lines
        lines = len(code.split('\n'))
        if lines > 500:
            issues.append({
                'type': 'complexity',
                'severity': 'medium',
                'message': f'File is large ({lines} lines) - consider splitting'
            })
        
        return issues
    
    def generate_report(self, result: dict) -> str:
        """Generate markdown report"""
        
        report = f"""# AIEL-T Validation Report

**File:** {result['file']}  
**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 🎯 G-Score: {result['g_score']}

**Tier:** {result['tier']}

---

## 📊 Component Scores

| Engine | Score | Weight |
|--------|-------|--------|
| Invariant | {result['components']['invariant']:.3f} | 30% |
| Pattern | {result['components']['pattern']:.3f} | 25% |
| Contract | {result['components']['contract']:.3f} | 25% |
| Scenario | {result['components']['scenario']:.3f} | 20% |

---

## 🔍 Issues Found

"""
        
        if result['issues']:
            for issue in result['issues']:
                report += f"### {issue['severity'].upper()}: {issue['type']}\n"
                report += f"{issue['message']}\n\n"
        else:
            report += "*No issues found!* ✅\n\n"
        
        report += """---

## 💡 Recommendations

"""
        
        if result['g_score'] >= 0.95:
            report += "✅ Excellent code quality! Ready for certification.\n"
        elif result['g_score'] >= 0.90:
            report += "✅ Good code quality. Production ready.\n"
        elif result['g_score'] >= 0.70:
            report += "⚠️ Acceptable quality. Consider improvements before production.\n"
        else:
            report += "❌ Needs significant improvement. Review before deployment.\n"
        
        report += f"\n---\n\n*Generated by AIEL-T Lite*\n"
        
        return report


def main():
    """Test G-Score Portal code!"""
    
    print("="*60)
    print("🎬 AIEL-T Lite - Meta Validation Test!")
    print("="*60)
    print("\nValidating G-Score Portal backend code...\n")
    
    # Target file
    target = "/home/claude/g-score-portal/backend/services/aiel_service.py"
    
    if not Path(target).exists():
        print(f"❌ File not found: {target}")
        return
    
    # Run validation
    validator = AIEL_T_Lite()
    result = validator.validate(target)
    
    # Print results
    print("🎯 Results:")
    print(f"   G-Score: {result['g_score']}")
    print(f"   Tier: {result['tier']}")
    print(f"\n📊 Component Scores:")
    for comp, score in result['components'].items():
        print(f"   {comp.capitalize()}: {score:.3f}")
    
    print(f"\n🔍 Issues: {len(result['issues'])}")
    for issue in result['issues']:
        print(f"   - [{issue['severity']}] {issue['message']}")
    
    # Generate report
    report = validator.generate_report(result)
    
    report_path = "/mnt/user-data/outputs/AIEL_T_VALIDATION_REPORT.md"
    with open(report_path, 'w') as f:
        f.write(report)
    
    print(f"\n📄 Full report: {report_path}")
    print("\n" + "="*60)
    print("✅ Meta validation complete!")
    print("="*60)
    print("\n😂 AI validated AI-generated code! INCEPTION! 🎬")


if __name__ == '__main__':
    main()
