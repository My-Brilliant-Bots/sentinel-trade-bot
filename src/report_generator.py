"""
Report generation module for creating formatted HTML reports
"""
from typing import List, Dict
from datetime import datetime

class ReportGenerator:
    """Generate HTML reports for trading signals"""
    
    def generate_stock_analysis_report(self, 
                                      signals: List[Dict],
                                      position_sizes: List[Dict],
                                      options: List[Dict],
                                      backtest_stats: Dict = None) -> str:
        """
        Generate comprehensive HTML report
        
        Args:
            signals: List of stock trading signals
            position_sizes: List of position sizing recommendations
            options: List of options recommendations
            backtest_stats: Optional backtest statistics
        
        Returns:
            HTML formatted report string
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Stock Analysis Report - {timestamp}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0;
            font-size: 32px;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
        }}
        .summary {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .summary h2 {{
            margin-top: 0;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .stock-card {{
            background: white;
            padding: 25px;
            margin-bottom: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 5px solid #667eea;
        }}
        .stock-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            border-bottom: 2px solid #f0f0f0;
            padding-bottom: 15px;
        }}
        .stock-symbol {{
            font-size: 28px;
            font-weight: bold;
            color: #667eea;
        }}
        .confidence {{
            background: #4CAF50;
            color: white;
            padding: 8px 15px;
            border-radius: 20px;
            font-weight: bold;
        }}
        .confidence.medium {{
            background: #FF9800;
        }}
        .confidence.low {{
            background: #F44336;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 20px 0;
        }}
        .metric {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 3px solid #667eea;
        }}
        .metric-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 20px;
            font-weight: bold;
            color: #333;
        }}
        .buy-signal {{
            background: #4CAF50;
            color: white;
            padding: 12px 25px;
            border-radius: 5px;
            display: inline-block;
            font-weight: bold;
            margin: 10px 0;
        }}
        .section {{
            margin: 25px 0;
        }}
        .section h3 {{
            color: #667eea;
            margin-bottom: 15px;
            font-size: 18px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #667eea;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .positive {{
            color: #4CAF50;
            font-weight: bold;
        }}
        .negative {{
            color: #F44336;
            font-weight: bold;
        }}
        .rationale {{
            background: #e8eaf6;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            border-left: 4px solid #667eea;
            font-style: italic;
        }}
        .options-card {{
            background: #fff3e0;
            padding: 20px;
            border-radius: 8px;
            margin: 15px 0;
            border-left: 4px solid #ff9800;
        }}
        .warning {{
            background: #fff3cd;
            border: 1px solid #ffc107;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #666;
            border-top: 2px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Stock Analysis Report</h1>
        <p>Generated: {timestamp}</p>
        <p>Strategy: RSI-2 Mean Reversion with Trend Filter</p>
    </div>
"""
        
        # Add summary section
        if signals:
            html += self._generate_summary_section(signals, position_sizes)
        
        # Add backtest results if available
        if backtest_stats:
            html += self._generate_backtest_section(backtest_stats)
        
        # Add individual stock sections
        if signals:
            for i, signal in enumerate(signals):
                position = position_sizes[i] if i < len(position_sizes) else None
                option = options[i] if i < len(options) else None
                html += self._generate_stock_section(signal, position, option)
        else:
            html += """
    <div class="stock-card">
        <h2>No Buy Signals Found</h2>
        <p>No stocks matched the criteria at this time. The strategy looks for:</p>
        <ul>
            <li>Price above 200-day moving average (uptrend)</li>
            <li>RSI-2 below 15 (oversold condition)</li>
            <li>Volume above average (confirmation)</li>
            <li>RSI-14 above 25 (avoid falling knives)</li>
        </ul>
        <p>Try again later or adjust the strategy parameters for different market conditions.</p>
    </div>
"""
        
        # Add disclaimer
        html += """
    <div class="warning">
        <strong>⚠️ Important Disclaimer:</strong><br>
        This report is for informational purposes only and should not be considered financial advice. 
        Past performance does not guarantee future results. Always conduct your own research and 
        consult with a qualified financial advisor before making investment decisions. Trading stocks 
        and options involves substantial risk of loss.
    </div>
    
    <div class="footer">
        <p>Automated Stock Analysis System</p>
        <p>For questions or support, please review the backtesting results and adjust parameters as needed.</p>
    </div>
</body>
</html>
"""
        
        return html
    
    def _generate_summary_section(self, signals: List[Dict], position_sizes: List[Dict]) -> str:
        """Generate executive summary section"""
        total_signals = len(signals)
        avg_confidence = sum(s['confidence_score'] for s in signals) / total_signals if total_signals > 0 else 0
        total_capital_required = sum(p['position_value'] for p in position_sizes) if position_sizes else 0
        total_risk = sum(p['total_risk_dollars'] for p in position_sizes) if position_sizes else 0
        
        html = f"""
    <div class="summary">
        <h2>Executive Summary</h2>
        <div class="metrics">
            <div class="metric">
                <div class="metric-label">Buy Signals</div>
                <div class="metric-value">{total_signals}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Avg Confidence</div>
                <div class="metric-value">{avg_confidence:.0f}%</div>
            </div>
            <div class="metric">
                <div class="metric-label">Capital Required</div>
                <div class="metric-value">${total_capital_required:,.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Total Risk</div>
                <div class="metric-value">${total_risk:,.2f}</div>
            </div>
        </div>
    </div>
"""
        return html
    
    def _generate_backtest_section(self, stats: Dict) -> str:
        """Generate backtest results section"""
        win_rate_class = "positive" if stats.get('win_rate_pct', 0) > 50 else "negative"
        
        html = f"""
    <div class="summary">
        <h2>📈 Backtesting Results</h2>
        <p>Historical performance of this strategy:</p>
        <div class="metrics">
            <div class="metric">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value {win_rate_class}">{stats.get('win_rate_pct', 0):.1f}%</div>
            </div>
            <div class="metric">
                <div class="metric-label">Total Trades</div>
                <div class="metric-value">{stats.get('total_trades', 0)}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Profit Factor</div>
                <div class="metric-value">{stats.get('profit_factor', 0):.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Avg Days Held</div>
                <div class="metric-value">{stats.get('avg_days_held', 0):.1f}</div>
            </div>
        </div>
    </div>
"""
        return html
    
    def _generate_stock_section(self, signal: Dict, position: Dict, option: Dict) -> str:
        """Generate individual stock analysis section"""
        confidence_class = ""
        if signal['confidence_score'] >= 70:
            confidence_class = ""
        elif signal['confidence_score'] >= 50:
            confidence_class = "medium"
        else:
            confidence_class = "low"
        
        html = f"""
    <div class="stock-card">
        <div class="stock-header">
            <div class="stock-symbol">{signal['symbol']}</div>
            <div class="confidence {confidence_class}">
                Confidence: {signal['confidence_score']:.0f}%
            </div>
        </div>
        
        <div class="buy-signal">🎯 BUY SIGNAL</div>
"""
        
        # Price and indicators section
        html += f"""
        <div class="section">
            <h3>Price & Technical Indicators</h3>
            <div class="metrics">
                <div class="metric">
                    <div class="metric-label">Current Price</div>
                    <div class="metric-value">${signal['entry_price']:.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">RSI-2</div>
                    <div class="metric-value">{signal['indicators']['rsi_2']:.1f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">RSI-14</div>
                    <div class="metric-value">{signal['indicators']['rsi_14']:.1f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">vs 200-day SMA</div>
                    <div class="metric-value positive">+{signal['indicators']['price_vs_sma_200']:.1f}%</div>
                </div>
            </div>
        </div>
"""
        
        # Position sizing section
        if position:
            html += f"""
        <div class="section">
            <h3>Position Sizing & Risk Management</h3>
            <table>
                <tr>
                    <th>Parameter</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Recommended Shares</td>
                    <td><strong>{position['recommended_shares']}</strong></td>
                </tr>
                <tr>
                    <td>Position Value</td>
                    <td>${position['position_value']:,.2f}</td>
                </tr>
                <tr>
                    <td>Entry Price</td>
                    <td>${position['entry_price']:.2f}</td>
                </tr>
                <tr>
                    <td>Stop Loss</td>
                    <td class="negative">${position['stop_loss']:.2f}</td>
                </tr>
                <tr>
                    <td>Take Profit 1 (50%)</td>
                    <td class="positive">${position['take_profit_1']:.2f}</td>
                </tr>
                <tr>
                    <td>Take Profit 2 (50%)</td>
                    <td class="positive">${position['take_profit_2']:.2f}</td>
                </tr>
                <tr style="background-color: #ffebee;">
                    <td><strong>Max Loss</strong></td>
                    <td class="negative"><strong>${position['total_risk_dollars']:.2f} ({position['risk_percentage']:.1f}%)</strong></td>
                </tr>
                <tr style="background-color: #e8f5e9;">
                    <td><strong>Potential Profit (TP2)</strong></td>
                    <td class="positive"><strong>${position['potential_profit_tp2']:.2f}</strong></td>
                </tr>
                <tr>
                    <td><strong>Risk:Reward Ratio</strong></td>
                    <td><strong>1:{position['risk_reward_ratio_tp2']:.1f}</strong></td>
                </tr>
            </table>
        </div>
"""
        
        # Options section
        if option and 'error' not in option:
            html += f"""
        <div class="section">
            <h3>Options Strategy Recommendation</h3>
            <div class="options-card">
                <h4>📋 {option['strategy']}</h4>
                <div class="metrics">
                    <div class="metric">
                        <div class="metric-label">Strike Price</div>
                        <div class="metric-value">${option['strike']:.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Expiration</div>
                        <div class="metric-value">{option['expiration']}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Premium</div>
                        <div class="metric-value">${option['premium']:.2f}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">DTE</div>
                        <div class="metric-value">{option['dte']} days</div>
                    </div>
                </div>
                
                <div class="rationale">
                    {option.get('recommendation_rationale', 'No rationale provided')}
                </div>
            </div>
        </div>
"""
        
        # Exit criteria
        html += f"""
        <div class="section">
            <h3>Exit Strategy</h3>
            <ul>
                <li><strong>Stop Loss:</strong> Exit if price falls to ${signal['stop_loss']:.2f}</li>
                <li><strong>Take Profit 1:</strong> Sell 50% at ${signal['take_profit_1']:.2f}</li>
                <li><strong>Take Profit 2:</strong> Sell remaining 50% at ${signal['take_profit_2']:.2f}</li>
                <li><strong>RSI Exit:</strong> Consider exiting if RSI-2 rises above {signal['exit_criteria']['rsi_2_above']}</li>
                <li><strong>Time Exit:</strong> Exit after {signal['exit_criteria']['days_in_trade_max']} days if targets not hit</li>
            </ul>
        </div>
    </div>
"""
        
        return html