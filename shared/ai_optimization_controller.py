"""
Controller for AI optimization settings and operations.

This module provides endpoints for:
1. Viewing AI optimization statistics and settings
2. Managing cache settings
3. Clearing the cache
4. Adjusting budget settings
"""

import os
import json
import logging
from flask import Blueprint, request, jsonify

ai_optimization_bp = Blueprint('ai_optimization', __name__)
logger = logging.getLogger('ai_optimization_controller')

# This will be set by the main application
optimized_openai_service = None

def init_controller(service):
    """Initialize the controller with a reference to the optimization service."""
    global optimized_openai_service
    optimized_openai_service = service
    logger.info("AI Optimization controller initialized")

@ai_optimization_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get AI optimization statistics."""
    if not optimized_openai_service:
        return jsonify({'error': 'Service not initialized'}), 500
        
    try:
        stats = optimized_openai_service.get_usage_statistics()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting AI optimization stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@ai_optimization_bp.route('/cache/clear', methods=['POST'])
def clear_cache():
    """Clear the AI response cache."""
    if not optimized_openai_service:
        return jsonify({'error': 'Service not initialized'}), 500
        
    try:
        result = optimized_openai_service.clear_cache()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error clearing AI cache: {str(e)}")
        return jsonify({'error': str(e)}), 500

@ai_optimization_bp.route('/settings', methods=['GET'])
def get_settings():
    """Get AI optimization settings."""
    if not optimized_openai_service:
        return jsonify({'error': 'Service not initialized'}), 500
        
    try:
        stats = optimized_openai_service.get_usage_statistics()
        settings = stats.get('config', {})
        
        # Add environment variable settings
        settings.update({
            'OPENAI_CACHE_TTL_SECONDS': int(os.environ.get('OPENAI_CACHE_TTL_SECONDS', 3600)),
            'OPENAI_ENABLE_CACHING': os.environ.get('OPENAI_ENABLE_CACHING', 'True').lower() == 'true',
            'OPENAI_DAILY_BUDGET': float(os.environ.get('OPENAI_DAILY_BUDGET', 10.0)),
            'OPENAI_MONTHLY_BUDGET': float(os.environ.get('OPENAI_MONTHLY_BUDGET', 300.0)),
            'OPENAI_DRAFT_MODEL': os.environ.get('OPENAI_DRAFT_MODEL', 'gpt-3.5-turbo'),
            'OPENAI_POLISH_MODEL': os.environ.get('OPENAI_POLISH_MODEL', 'gpt-4o')
        })
        
        return jsonify(settings)
    except Exception as e:
        logger.error(f"Error getting AI optimization settings: {str(e)}")
        return jsonify({'error': str(e)}), 500

@ai_optimization_bp.route('/settings', methods=['POST'])
def update_settings():
    """Update AI optimization settings."""
    if not optimized_openai_service:
        return jsonify({'error': 'Service not initialized'}), 500
        
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        # Update settings through environment variables
        # These will be used next time the service restarts
        
        # Update cache settings
        if 'OPENAI_CACHE_TTL_SECONDS' in data:
            os.environ['OPENAI_CACHE_TTL_SECONDS'] = str(int(data['OPENAI_CACHE_TTL_SECONDS']))
            
        if 'OPENAI_ENABLE_CACHING' in data:
            os.environ['OPENAI_ENABLE_CACHING'] = str(bool(data['OPENAI_ENABLE_CACHING'])).lower()
            
        # Update budget settings
        if 'OPENAI_DAILY_BUDGET' in data:
            os.environ['OPENAI_DAILY_BUDGET'] = str(float(data['OPENAI_DAILY_BUDGET']))
            optimized_openai_service.daily_budget = float(data['OPENAI_DAILY_BUDGET'])
            
        if 'OPENAI_MONTHLY_BUDGET' in data:
            os.environ['OPENAI_MONTHLY_BUDGET'] = str(float(data['OPENAI_MONTHLY_BUDGET']))
            optimized_openai_service.monthly_budget = float(data['OPENAI_MONTHLY_BUDGET'])
        
        # Update model settings
        if 'OPENAI_DRAFT_MODEL' in data:
            os.environ['OPENAI_DRAFT_MODEL'] = data['OPENAI_DRAFT_MODEL']
            
        if 'OPENAI_POLISH_MODEL' in data:
            os.environ['OPENAI_POLISH_MODEL'] = data['OPENAI_POLISH_MODEL']
            
        return jsonify({'success': True, 'message': 'Settings updated'})
    except Exception as e:
        logger.error(f"Error updating AI optimization settings: {str(e)}")
        return jsonify({'error': str(e)}), 500

@ai_optimization_bp.route('/validate/prompt', methods=['POST'])
def validate_prompt():
    """
    Validate and analyze a prompt to determine token usage and estimated cost.
    Useful for prompt engineering and cost estimation.
    """
    if not optimized_openai_service:
        return jsonify({'error': 'Service not initialized'}), 500
        
    try:
        data = request.json
        if not data or 'prompt' not in data:
            return jsonify({'error': 'No prompt provided'}), 400
            
        prompt = data['prompt']
        model = data.get('model', 'gpt-3.5-turbo')
        
        # Count tokens
        token_count = optimized_openai_service.optimization_service.count_tokens(prompt, model)
        
        # Determine average token cost for the model
        input_cost_per_1k, output_cost_per_1k = optimized_openai_service.model_costs.get(
            model, optimized_openai_service.model_costs['gpt-3.5-turbo']
        )
        
        # Estimate costs
        input_cost = (token_count / 1000) * input_cost_per_1k
        
        # Estimated output tokens (usually 1.5x input, but can vary)
        estimated_output_tokens = int(token_count * 1.5)
        output_cost = (estimated_output_tokens / 1000) * output_cost_per_1k
        
        total_estimated_cost = input_cost + output_cost
        
        return jsonify({
            'prompt_tokens': token_count,
            'estimated_output_tokens': estimated_output_tokens,
            'input_cost': round(input_cost, 5),
            'output_cost': round(output_cost, 5),
            'total_estimated_cost': round(total_estimated_cost, 5),
            'model': model,
            'within_budget': total_estimated_cost <= optimized_openai_service.daily_budget
        })
    except Exception as e:
        logger.error(f"Error validating prompt: {str(e)}")
        return jsonify({'error': str(e)}), 500