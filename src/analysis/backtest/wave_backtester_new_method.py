    def check_stop_loss_take_profit(
        self, 
        symbol: str, 
        date: str, 
        price: float, 
        data_idx: int = 0,
        wave_signal: Optional[UnifiedWaveSignal] = None,
        is_limit_down: bool = False  # 跌停无法卖出
    ):
        """
        检查止损止盈 - 适配 UnifiedWaveSignal + 涨跌停处理 + 移动止盈
        """
        if symbol not in self.positions:
            return None
        
        # 跌停无法卖出
        if is_limit_down:
            return None
        
        trade = self.positions[symbol]
        
        # 检查最小持仓天数
        holding_days = trade.holding_days(data_idx)
        if holding_days < self.min_holding_days:
            return None
        
        # 1. 固定止损检查
        if trade.stop_loss and price <= trade.stop_loss:
            self.execute_trade(symbol, date, price, TradeAction.CLOSE, data_idx=data_idx, is_limit_down=is_limit_down, reason="stop_loss")
            return "stop_loss"
        
        # 2. 移动止盈逻辑
        if self.use_trailing_stop and trade.target_price:
            target_threshold = trade.target_price * self.trailing_stop_activation
            
            # 首次达到目标价阈值，启动移动止盈
            if not trade.target_hit and price >= target_threshold:
                trade.target_hit = True
                trade.target_hit_price = price
                trade.target_hit_idx = data_idx
                trade.highest_price = price
                # 设置初始移动止盈价位（从最高点回撤 trailing_stop_pct）
                trade.trailing_stop_price = price * (1 - self.trailing_stop_pct)
                return None  # 继续持仓，启动移动止盈跟踪
            
            # 已经启动移动止盈，更新最高价和移动止盈价位
            if trade.target_hit:
                # 更新最高价
                if price > trade.highest_price:
                    trade.highest_price = price
                    # 更新移动止盈价位（从新的最高点回撤 trailing_stop_pct）
                    trade.trailing_stop_price = price * (1 - self.trailing_stop_pct)
                
                # 检查是否触发移动止盈
                if trade.trailing_stop_price and price <= trade.trailing_stop_price:
                    self.execute_trade(symbol, date, price, TradeAction.CLOSE, data_idx=data_idx, is_limit_down=is_limit_down, 
                                     reason=f"trailing_stop({trade.trailing_stop_price:.2f})")
                    return f"trailing_stop({trade.trailing_stop_price:.2f})"
        
        # 3. 原动态止盈逻辑（当不启用移动止盈或作为备选）
        if not self.use_trailing_stop and trade.target_price:
            distance_to_target = abs(trade.target_price - price) / price
            
            if distance_to_target <= self.target_proximity_pct:
                self.execute_trade(symbol, date, price, TradeAction.CLOSE, data_idx=data_idx, is_limit_down=is_limit_down, reason=f"target_proximity")
                return f"target_proximity({trade.target_price:.2f})"
            
            if price >= trade.target_price:
                self.execute_trade(symbol, date, price, TradeAction.CLOSE, data_idx=data_idx, is_limit_down=is_limit_down, reason="target_reached")
                return f"target_reached({trade.target_price:.2f})"
        
        return None

    def _calculate_stock_volatility