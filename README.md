# Sleep-Trading

An auto trading framework for building, backtesting, and running algorithmic trading strategies.

## Overview

Sleep-Trading provides a lightweight foundation for automating trading workflows. Define strategies once, backtest them against historical data, and deploy them against paper or live markets — so your portfolio can work while you sleep.

## Features

- Strategy definition and execution
- Backtesting engine
- Live and paper trading support
- Configurable data sources and brokers
- Modular architecture for easy extension

## Project Structure

```
sleep-trading/
├── README.md
├── src/           # framework source code
├── strategies/    # user-defined trading strategies
├── data/          # market data and cached feeds
├── config/        # runtime configuration
└── tests/         # unit and integration tests
```

*Layout will evolve as the framework grows.*

## Getting Started

```bash
git clone https://github.com/JerryIshihara/sleep-trading.git
cd sleep-trading
# install dependencies (TBD)
```

## Usage

```bash
# run a strategy (TBD)
sleep-trading run --strategy my_strategy --mode paper
```

## License

TBD
