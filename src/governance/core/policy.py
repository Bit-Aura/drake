import yaml
from pathlib import Path
from typing import Dict, Any
import ast

class PolicyEngine:
    """Evaluates workflows against governance policies defined in policy.yaml."""

    def __init__(self, policy_path: str | None = None):
        if not policy_path:
            policy_path = str(Path(__file__).resolve().parent.parent / "config" / "policy.yaml")
        
        self.config = self._load_policy(policy_path)
        self.rules = self.config.get("rules", [])

    def _load_policy(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f)
        except Exception:
            # Fallback to empty if not found, let defaults handle it
            return {}

    def get_config(self) -> Dict[str, Any]:
        return self.config

    def evaluate(self, workflow_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates the workflow context against rules.
        workflow_context should contain 'risk_level', 'is_read_only', 'actions', 'is_bulk', etc.
        Returns: {"status": 0|1|2, "reason": str}
        where 0 = Pending, 1 = Approved, 2 = Rejected
        """
        # Default to pending
        result_status = 0
        rejection_reason = None

        # Build local scope for eval
        eval_locals = {
            "workflow": type("WorkflowContext", (), workflow_context)()
        }

        for rule in self.rules:
            condition_expr = rule.get("condition", "False")
            action = rule.get("action")
            
            try:
                def _eval(node, context):
                    if isinstance(node, ast.Constant): return node.value
                    elif isinstance(node, ast.Name): return context.get(node.id)
                    elif isinstance(node, ast.Attribute):
                        val = _eval(node.value, context)
                        if isinstance(val, dict): return val.get(node.attr)
                        return getattr(val, node.attr, None)
                    elif isinstance(node, ast.Compare):
                        left = _eval(node.left, context)
                        for op, right_node in zip(node.ops, node.comparators):
                            right = _eval(right_node, context)
                            if isinstance(op, ast.Eq):
                                if left != right: return False
                            elif isinstance(op, ast.NotEq):
                                if left == right: return False
                            elif isinstance(op, ast.In):
                                if not right or left not in right: return False
                            elif isinstance(op, ast.NotIn):
                                if right and left in right: return False
                            left = right
                        return True
                    elif isinstance(node, ast.BoolOp):
                        if isinstance(node.op, ast.And): return all(_eval(v, context) for v in node.values)
                        elif isinstance(node.op, ast.Or): return any(_eval(v, context) for v in node.values)
                    raise ValueError("Unsupported AST node")

                tree = ast.parse(condition_expr, mode='eval').body
                is_match = _eval(tree, eval_locals)
                
                if is_match:
                    if action == "DENY":
                        return {"status": 2, "reason": rule.get("reason", "Denied by policy rule: " + rule.get("name", ""))}
                    elif action == "AUTO_APPROVE":
                        result_status = 1
                    elif action == "REQUIRE_APPROVAL":
                        result_status = 0
            except Exception as e:
                # Log or handle eval errors
                import logging
                logging.debug(f"Policy eval failed: {e}")

        return {"status": result_status, "reason": rejection_reason}
