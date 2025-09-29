import os
import re
from pathlib import Path

class CodeAnalyzer:
    def analyze_file(self, file_path: str):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        lines = content.split('\n')
        total_lines = len(lines)
        code_lines = len([l for l in lines if l.strip() and not l.strip().startswith(('#', '//', '/*', '*'))])
        comment_lines = len([l for l in lines if l.strip().startswith(('#', '//', '/*', '*'))])
        
        complexity = 1 + sum(len(re.findall(rf'\b{k}\b', content, re.IGNORECASE)) 
                           for k in ['if', 'for', 'while', 'try', 'case'])
        
        difficulty = min(10, 1 + len([k for k in ['async', 'threading', 'regex'] if k in content.lower()]) + 
                        (2 if code_lines > 200 else 1 if code_lines > 100 else 0))
        
        levels = ["Entry", "Junior", "Mid", "Senior", "Architect"]
        dev_level = levels[min(4, (difficulty - 1) // 2)]
        
        ext = Path(file_path).suffix
        tech_stack = []
        if ext in {'.py': 'Python', '.js': 'JavaScript', '.cpp': 'C++', '.java': 'Java'}.keys():
            tech_stack.append({'.py': 'Python', '.js': 'JavaScript', '.cpp': 'C++', '.java': 'Java'}[ext])
        
        return {
            'file_path': file_path,
            'total_lines': total_lines,
            'code_lines': code_lines,
            'comment_lines': comment_lines,
            'code_comment_ratio': round(code_lines / max(comment_lines, 1), 2),
            'cyclomatic_complexity': min(complexity, 50),
            'maintainability_index': max(0, min(100, int(100 - max(0, (code_lines - 100) / 10) + (comment_lines / max(total_lines, 1)) * 20))),
            'estimated_dev_hours': round(code_lines * 0.1, 1),
            'difficulty_score': difficulty,
            'developer_level': dev_level,
            'pattern_score': min(10, 1 + len([p for p in ['class', 'interface', 'factory'] if p in content.lower()])),
            'optimization_score': min(10, 5 + len([o for o in ['cache', 'async', 'parallel'] if o in content.lower()])),
            'best_practices_score': min(10, 1 + len([b for b in ['try:', 'def ', 'class '] if b in content])),
            'tech_stack': tech_stack
        }
    
    def analyze_project(self, project_path: str):
        results = []
        for root, dirs, files in os.walk(project_path):
            for file in files:
                if Path(file).suffix in {'.py', '.js', '.java', '.cpp', '.c', '.cs', '.php', '.rb', '.go', '.ts'}:
                    results.append(self.analyze_file(os.path.join(root, file)))
        
        if results:
            summary = {
                'total_files': len(results),
                'total_lines': sum(r['total_lines'] for r in results),
                'avg_complexity': round(sum(r['cyclomatic_complexity'] for r in results) / len(results), 2),
                'total_estimated_hours': round(sum(r['estimated_dev_hours'] for r in results), 1),
                'max_difficulty': max(r['difficulty_score'] for r in results)
            }
        else:
            summary = {}
        
        return {'files': results, 'summary': summary}
