"""
AIEL-T Report Generator v1.0
=============================

Generates formatted reports from AIEL-T results.
Supports: JSON, Markdown, HTML
"""

import json
from typing import Dict, Any
from pathlib import Path
from datetime import datetime


class ReportGenerator:
    """
    Generate formatted reports from AIEL-T test results
    """
    
    @staticmethod
    def generate_markdown(results: Dict[str, Any], output_file: str = None) -> str:
        """
        Generate Markdown report
        
        Args:
            results: AIEL-T test results
            output_file: Optional path to save report
            
        Returns:
            Markdown string
        """
        md = []
        
        # Header
        md.append("# 🧪 AIEL-T v1.0 Test Report")
        md.append("")
        md.append(f"**Generated:** {results.get('timestamp', 'N/A')}")
        md.append(f"**G-Score:** {results.get('G_score', 0.0):.4f}")
        md.append(f"**Status:** {results.get('status', 'UNKNOWN')}")
        md.append("")
        
        # Status badge
        status = results.get('status', 'UNKNOWN')
        if status == 'DEPLOYABLE':
            badge = "🟢 **DEPLOYABLE**"
        elif status == 'REVISION_REQUIRED':
            badge = "🟡 **REVISION REQUIRED**"
        else:
            badge = "🔴 **REJECT**"
        md.append(badge)
        md.append("")
        md.append("---")
        md.append("")
        
        # Summary
        summary = results.get('summary', {})
        md.append("## 📊 Summary")
        md.append("")
        
        breakdown = summary.get('breakdown', {})
        md.append("| Engine | Score | Weight | Details |")
        md.append("|--------|-------|--------|---------|")
        
        for engine_name, engine_data in breakdown.items():
            score = engine_data.get('score', 0.0)
            weight = engine_data.get('weight', 0.0)
            
            if engine_name == 'invariants':
                details = f"{engine_data.get('passed', 0)}/{engine_data.get('total', 0)} passed"
            elif engine_name == 'patterns':
                details = f"{engine_data.get('passed', 0)}/{engine_data.get('total', 0)} passed"
            elif engine_name == 'contracts':
                details = f"{engine_data.get('matched', 0)}/{engine_data.get('total', 0)} valid"
            elif engine_name == 'scenarios':
                details = f"{engine_data.get('passed', 0)}/{engine_data.get('triggered', 0)} triggered"
            else:
                details = "N/A"
            
            md.append(f"| {engine_name.capitalize()} | {score:.4f} | {weight:.0%} | {details} |")
        
        md.append("")
        md.append("---")
        md.append("")
        
        # Recommendations
        md.append("## 💡 Recommendations")
        md.append("")
        for rec in summary.get('recommendations', []):
            md.append(f"- {rec}")
        md.append("")
        md.append("---")
        md.append("")
        
        # Detailed Results
        md.append("## 🔍 Detailed Results")
        md.append("")
        
        # Invariants
        md.append("### 1. Invariants Engine")
        md.append("")
        inv_results = results.get('invariants', {}).get('results', {})
        if inv_results:
            md.append("| Invariant | Status |")
            md.append("|-----------|--------|")
            for inv_id, status in inv_results.items():
                emoji = "✅" if status == "PASS" else "❌"
                md.append(f"| {inv_id} | {emoji} {status} |")
        else:
            md.append("*No invariant results*")
        md.append("")
        
        # Patterns
        md.append("### 2. Pattern Engine")
        md.append("")
        pattern_results = results.get('patterns', {}).get('results', {})
        if pattern_results:
            md.append("| Pattern | Score | Status |")
            md.append("|---------|-------|--------|")
            for pattern_name, pattern_data in pattern_results.items():
                score = pattern_data.get('score', 0.0)
                status = pattern_data.get('status', 'UNKNOWN')
                emoji = "✅" if status == "PASS" else "⚠️" if status == "WARN" else "❌"
                md.append(f"| {pattern_name} | {score:.4f} | {emoji} {status} |")
        else:
            md.append("*No pattern results*")
        md.append("")
        
        # Contracts
        md.append("### 3. Contract Engine")
        md.append("")
        contract_results = results.get('contracts', {}).get('results', {})
        if contract_results:
            md.append("| Field | Status |")
            md.append("|-------|--------|")
            for field_name, status in contract_results.items():
                emoji = "✅" if status == "PASS" else "❌"
                md.append(f"| {field_name} | {emoji} {status} |")
        else:
            md.append("*No contract results*")
        md.append("")
        
        # Scenarios
        md.append("### 4. Scenario Engine")
        md.append("")
        scenario_results = results.get('scenarios', {}).get('results', [])
        if scenario_results:
            md.append("| Scenario | Triggered | Status |")
            md.append("|----------|-----------|--------|")
            for scenario in scenario_results:
                triggered = scenario.get('condition_triggered', False)
                status = scenario.get('status', 'UNKNOWN')
                emoji = "✅" if status == "PASS" else "⚠️" if status == "N/A" else "❌"
                trig_text = "Yes" if triggered else "No"
                md.append(f"| {scenario.get('id', 'N/A')} | {trig_text} | {emoji} {status} |")
        else:
            md.append("*No scenario results*")
        md.append("")
        
        # Failures
        if summary.get('total_failures', 0) > 0:
            md.append("---")
            md.append("")
            md.append("## ⚠️ Failures")
            md.append("")
            md.append(f"**Total Failures:** {summary['total_failures']}")
            md.append("")
            
            failures = summary.get('failures', [])
            if failures:
                md.append("### Top Failures")
                md.append("")
                for i, failure in enumerate(failures[:10], 1):
                    engine = failure.get('engine', 'unknown')
                    md.append(f"{i}. **[{engine.upper()}]** {failure.get('id', 'N/A')}")
                    if 'rule' in failure:
                        md.append(f"   - Rule: {failure['rule']}")
                    if 'issue' in failure:
                        md.append(f"   - Issue: {failure['issue']}")
                    md.append("")
        
        md.append("---")
        md.append("")
        md.append("*Generated by AIEL-T v1.0*")
        
        report = "\n".join(md)
        
        # Save if output file provided _odl--> with open(output_file, 'w') as f:
        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
        
        return report
    
    @staticmethod
    def generate_html(results: Dict[str, Any], output_file: str = None) -> str:
        """
        Generate HTML report
        
        Args:
            results: AIEL-T test results
            output_file: Optional path to save report
            
        Returns:
            HTML string
        """
        g_score = results.get('G_score', 0.0)
        status = results.get('status', 'UNKNOWN')
        summary = results.get('summary', {})
        
        # Status color
        if status == 'DEPLOYABLE':
            status_color = '#28a745'
            status_icon = '✓'
        elif status == 'REVISION_REQUIRED':
            status_color = '#ffc107'
            status_icon = '!'
        else:
            status_color = '#dc3545'
            status_icon = '✗'
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIEL-T Test Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 40px;
            border-bottom: 3px solid #007bff;
            padding-bottom: 20px;
        }}
        
        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
            color: #007bff;
        }}
        
        .status-badge {{
            display: inline-block;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 1.5em;
            font-weight: bold;
            color: white;
            background: {status_color};
            margin: 20px 0;
        }}
        
        .g-score {{
            font-size: 3em;
            font-weight: bold;
            color: {status_color};
            margin: 20px 0;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        
        .summary-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #007bff;
        }}
        
        .summary-card h3 {{
            color: #007bff;
            margin-bottom: 10px;
        }}
        
        .summary-card .score {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }}
        
        .summary-card .details {{
            color: #666;
            margin-top: 5px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        
        th {{
            background: #007bff;
            color: white;
            font-weight: bold;
        }}
        
        tr:hover {{
            background: #f8f9fa;
        }}
        
        .pass {{ color: #28a745; font-weight: bold; }}
        .warn {{ color: #ffc107; font-weight: bold; }}
        .fail {{ color: #dc3545; font-weight: bold; }}
        
        .recommendations {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 20px;
            margin: 30px 0;
            border-radius: 4px;
        }}
        
        .recommendations h2 {{
            color: #856404;
            margin-bottom: 15px;
        }}
        
        .recommendations ul {{
            margin-left: 20px;
        }}
        
        .recommendations li {{
            margin: 10px 0;
        }}
        
        .section {{
            margin: 40px 0;
        }}
        
        .section h2 {{
            color: #007bff;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 AIEL-T v1.0 Test Report</h1>
            <div class="g-score">{g_score:.4f}</div>
            <div class="status-badge">{status_icon} {status}</div>
            <p>Generated: {results.get('timestamp', 'N/A')}</p>
        </div>
"""
        
        # Summary Grid
        html += """
        <div class="summary-grid">
"""
        
        breakdown = summary.get('breakdown', {})
        for engine_name, engine_data in breakdown.items():
            score = engine_data.get('score', 0.0)
            weight = engine_data.get('weight', 0.0)
            
            if engine_name == 'invariants':
                details = f"{engine_data.get('passed', 0)}/{engine_data.get('total', 0)} passed"
            elif engine_name == 'patterns':
                details = f"{engine_data.get('passed', 0)}/{engine_data.get('total', 0)} passed"
            elif engine_name == 'contracts':
                details = f"{engine_data.get('matched', 0)}/{engine_data.get('total', 0)} valid"
            elif engine_name == 'scenarios':
                details = f"{engine_data.get('passed', 0)}/{engine_data.get('triggered', 0)} triggered"
            else:
                details = "N/A"
            
            html += f"""
            <div class="summary-card">
                <h3>{engine_name.capitalize()}</h3>
                <div class="score">{score:.4f}</div>
                <div class="details">Weight: {weight:.0%}</div>
                <div class="details">{details}</div>
            </div>
"""
        
        html += """
        </div>
"""
        
        # Recommendations
        html += """
        <div class="recommendations">
            <h2>💡 Recommendations</h2>
            <ul>
"""
        for rec in summary.get('recommendations', []):
            html += f"                <li>{rec}</li>\n"
        
        html += """
            </ul>
        </div>
"""
        
        # Detailed Results - Invariants
        html += """
        <div class="section">
            <h2>1. Invariants Engine</h2>
            <table>
                <thead>
                    <tr>
                        <th>Invariant ID</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
"""
        
        inv_results = results.get('invariants', {}).get('results', {})
        for inv_id, status_val in inv_results.items():
            status_class = 'pass' if status_val == 'PASS' else 'fail'
            html += f"""
                    <tr>
                        <td>{inv_id}</td>
                        <td class="{status_class}">{status_val}</td>
                    </tr>
"""
        
        html += """
                </tbody>
            </table>
        </div>
"""
        
        # Footer
        html += """
        <div class="footer">
            <p>Generated by AIEL-T v1.0 Framework</p>
            <p>AIEL Factory © 2024</p>
        </div>
    </div>
</body>
</html>
"""
        
        # Save if output file provided odl_with open(output_file, 'w') as f:
        if output_file:
            Path(output_file).parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html)
        
        return html


if __name__ == "__main__":
    # Test report generation
    sample_results = {
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'G_score': 0.92,
        'status': 'REVISION_REQUIRED',
        'invariants': {
            'invariant_pass_rate': 1.0,
            'results': {
                'INV_001': 'PASS',
                'INV_002': 'PASS'
            },
            'passed': 2,
            'total': 2
        },
        'patterns': {
            'pattern_score': 0.85,
            'results': {
                'latency': {'score': 0.9, 'status': 'PASS'},
                'monotonicity': {'score': 0.8, 'status': 'PASS'}
            },
            'passed': 2,
            'total': 2
        },
        'contracts': {
            'contract_score': 0.95,
            'results': {
                'risk_factor_scalar': 'PASS',
                'broker_trust_score': 'PASS'
            },
            'matched': 2,
            'total': 2
        },
        'scenarios': {
            'scenario_score': 0.80,
            'results': [
                {'id': 'SC_001', 'condition_triggered': True, 'status': 'PASS'}
            ],
            'passed': 1,
            'triggered': 1
        },
        'summary': {
            'breakdown': {
                'invariants': {'score': 1.0, 'weight': 0.45, 'passed': 2, 'total': 2},
                'patterns': {'score': 0.85, 'weight': 0.15, 'passed': 2, 'total': 2},
                'contracts': {'score': 0.95, 'weight': 0.10, 'matched': 2, 'total': 2},
                'scenarios': {'score': 0.80, 'weight': 0.30, 'passed': 1, 'triggered': 1}
            },
            'recommendations': [
                '⚠️  Patterns: 85.0% score - Review behavioral patterns and stability',
                '⚠️  Scenarios: 80.0% pass rate - Fix resilience issues in critical scenarios'
            ],
            'total_failures': 0
        }
    }
    
    # Generate reports
    md_report = ReportGenerator.generate_markdown(sample_results, '/home/claude/report.md')
    html_report = ReportGenerator.generate_html(sample_results, '/home/claude/report.html')
    
    print("Reports generated successfully!")
    print("- report.md")
    print("- report.html")
