"""Entry point. Usage: python3.12 run.py"""
import asyncio

from src.demo import run_demo

if __name__ == "__main__":
    asyncio.run(run_demo())
