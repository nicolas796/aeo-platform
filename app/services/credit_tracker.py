"""Credit tracking and usage billing service"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from app.models import db, Tenant

class CreditTracker:
    """Track API usage and credits per tenant for billing"""
    
    # Credit costs for different operations
    COSTS = {
        'scan_keyword': 1,           # Per keyword scanned
        'scan_citation_check': 2,    # Per citation verification
        'content_generate': 10,      # Per article generated
        'keyword_discover': 5,       # Per keyword discovered via AI
        'competitor_analyze': 8,     # Per competitor analysis
        'report_generate': 3,        # Per report generated
        'email_send': 1,             # Per email sent
    }
    
    @classmethod
    def get_tenant_credits(cls, tenant_id: int) -> Dict:
        """Get current credit balance and usage for tenant"""
        from app.models import CreditBalance, CreditTransaction
        
        balance = CreditBalance.query.filter_by(tenant_id=tenant_id).first()
        if not balance:
            # Create default balance
            balance = CreditBalance(
                tenant_id=tenant_id,
                credits_total=1000,  # Starting credits
                credits_used=0,
                credits_remaining=1000,
                billing_cycle_start=datetime.utcnow(),
                billing_cycle_end=datetime.utcnow() + timedelta(days=30)
            )
            db.session.add(balance)
            db.session.commit()
        
        # Get recent transactions
        transactions = CreditTransaction.query.filter_by(
            tenant_id=tenant_id
        ).order_by(CreditTransaction.created_at.desc()).limit(50).all()
        
        return {
            'balance': {
                'total': balance.credits_total,
                'used': balance.credits_used,
                'remaining': balance.credits_remaining,
                'cycle_start': balance.billing_cycle_start,
                'cycle_end': balance.billing_cycle_end
            },
            'transactions': [t.to_dict() for t in transactions],
            'costs': cls.COSTS
        }
    
    @classmethod
    def charge(cls, tenant_id: int, operation: str, quantity: int = 1, 
               description: str = None, metadata: Dict = None) -> Dict:
        """Charge credits for an operation
        
        Returns:
            Dict with success status, remaining credits, and error if any
        """
        from app.models import CreditBalance, CreditTransaction
        
        cost_per_unit = cls.COSTS.get(operation, 1)
        total_cost = cost_per_unit * quantity
        
        # Get or create balance
        balance = CreditBalance.query.filter_by(tenant_id=tenant_id).first()
        if not balance:
            balance = CreditBalance(
                tenant_id=tenant_id,
                credits_total=1000,
                credits_used=0,
                credits_remaining=1000,
                billing_cycle_start=datetime.utcnow(),
                billing_cycle_end=datetime.utcnow() + timedelta(days=30)
            )
            db.session.add(balance)
        
        # Check if sufficient credits
        if balance.credits_remaining < total_cost:
            return {
                'success': False,
                'error': 'Insufficient credits',
                'required': total_cost,
                'remaining': balance.credits_remaining
            }
        
        # Deduct credits
        balance.credits_used += total_cost
        balance.credits_remaining -= total_cost
        
        # Create transaction record
        transaction = CreditTransaction(
            tenant_id=tenant_id,
            operation=operation,
            quantity=quantity,
            cost_per_unit=cost_per_unit,
            total_cost=total_cost,
            description=description or f'{operation} x{quantity}',
            metadata=metadata or {},
            balance_after=balance.credits_remaining
        )
        db.session.add(transaction)
        db.session.commit()
        
        return {
            'success': True,
            'charged': total_cost,
            'remaining': balance.credits_remaining,
            'transaction_id': transaction.id
        }
    
    @classmethod
    def add_credits(cls, tenant_id: int, amount: int, 
                    source: str = 'purchase', description: str = None) -> Dict:
        """Add credits to tenant account (for purchases, refunds, etc.)"""
        from app.models import CreditBalance, CreditTransaction
        
        balance = CreditBalance.query.filter_by(tenant_id=tenant_id).first()
        if not balance:
            balance = CreditBalance(
                tenant_id=tenant_id,
                credits_total=amount,
                credits_used=0,
                credits_remaining=amount,
                billing_cycle_start=datetime.utcnow(),
                billing_cycle_end=datetime.utcnow() + timedelta(days=30)
            )
            db.session.add(balance)
        else:
            balance.credits_total += amount
            balance.credits_remaining += amount
        
        # Create transaction record (negative cost = credit)
        transaction = CreditTransaction(
            tenant_id=tenant_id,
            operation='credit_add',
            quantity=1,
            cost_per_unit=0,
            total_cost=-amount,  # Negative = credit added
            description=description or f'Credit purchase: {amount} credits',
            metadata={'source': source, 'amount': amount},
            balance_after=balance.credits_remaining
        )
        db.session.add(transaction)
        db.session.commit()
        
        return {
            'success': True,
            'added': amount,
            'new_balance': balance.credits_remaining
        }
    
    @classmethod
    def get_usage_summary(cls, tenant_id: int, days: int = 30) -> Dict:
        """Get usage summary for the last N days"""
        from app.models import CreditTransaction
        from sqlalchemy import func
        
        since = datetime.utcnow() - timedelta(days=days)
        
        # Get total usage by operation
        usage_by_operation = db.session.query(
            CreditTransaction.operation,
            func.sum(CreditTransaction.quantity).label('total_quantity'),
            func.sum(CreditTransaction.total_cost).label('total_cost')
        ).filter(
            CreditTransaction.tenant_id == tenant_id,
            CreditTransaction.created_at >= since,
            CreditTransaction.total_cost > 0  # Exclude credit additions
        ).group_by(CreditTransaction.operation).all()
        
        return {
            'period_days': days,
            'operations': {
                op: {
                    'quantity': qty,
                    'cost': cost
                } for op, qty, cost in usage_by_operation
            },
            'total_cost': sum(cost for _, _, cost in usage_by_operation)
        }
