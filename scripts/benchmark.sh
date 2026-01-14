#!/bin/bash
# Run benchmarks for obskit
# 
# Usage:
#   ./scripts/benchmark.sh              # Run all benchmarks
#   ./scripts/benchmark.sh metrics      # Run only metrics benchmarks
#   ./scripts/benchmark.sh --compare    # Compare with saved baseline
#   ./scripts/benchmark.sh --json       # Output JSON results

set -e

cd "$(dirname "$0")/.."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# Box drawing characters
BOX_TL="╔"
BOX_TR="╗"
BOX_BL="╚"
BOX_BR="╝"
BOX_H="═"
BOX_V="║"
BOX_LT="╠"
BOX_RT="╣"
BOX_TT="╦"
BOX_BT="╩"
BOX_CROSS="╬"

print_header() {
    echo ""
    echo -e "${BOLD}${BLUE}"
    echo "╔══════════════════════════════════════════════════════════════════════════════╗"
    echo "║                        🏃 OBSKIT BENCHMARK SUITE                             ║"
    echo "╚══════════════════════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_section() {
    local title="$1"
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${CYAN}  $title${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_summary_table() {
    local json_file="$1"
    
    if [ ! -f "$json_file" ]; then
        return
    fi
    
    echo ""
    echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║                                    📊 BENCHMARK SUMMARY                                          ║${NC}"
    echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${BOLD}${GREEN}║  Test Name                                    │   Min    │   Mean   │  Median  │    OPS/s        ║${NC}"
    echo -e "${BOLD}${GREEN}╠═══════════════════════════════════════════════╪══════════╪══════════╪══════════╪═════════════════╣${NC}"
    
    # Parse JSON and format nicely
    python3 << EOF
import json
import sys

try:
    with open("$json_file", "r") as f:
        data = json.load(f)
    
    benchmarks = data.get("benchmarks", [])
    
    # Group by benchmark group
    groups = {}
    for b in benchmarks:
        group = b.get("group", "other")
        if group not in groups:
            groups[group] = []
        groups[group].append(b)
    
    # Status indicators
    def get_status(ops):
        if ops > 1000000:  # > 1M ops/s
            return "🟢"
        elif ops > 100000:  # > 100K ops/s
            return "🟡"
        else:
            return "🔴"
    
    def format_time(ns):
        if ns < 1000:
            return f"{ns:.1f} ns"
        elif ns < 1000000:
            return f"{ns/1000:.2f} µs"
        else:
            return f"{ns/1000000:.2f} ms"
    
    def format_ops(ops):
        if ops > 1000000:
            return f"{ops/1000000:.2f}M"
        elif ops > 1000:
            return f"{ops/1000:.1f}K"
        else:
            return f"{ops:.0f}"
    
    for group_name, group_benchmarks in sorted(groups.items()):
        # Print group header
        print(f"\033[1;32m║  \033[1;36m▸ {group_name.upper():<43}\033[1;32m │          │          │          │                 ║\033[0m")
        
        for b in sorted(group_benchmarks, key=lambda x: x["stats"]["mean"]):
            name = b["name"].replace("test_", "")[:40]
            stats = b["stats"]
            
            min_ns = stats["min"] * 1e9
            mean_ns = stats["mean"] * 1e9
            median_ns = stats["median"] * 1e9
            ops = stats["ops"]
            
            status = get_status(ops)
            
            min_str = format_time(min_ns)
            mean_str = format_time(mean_ns)
            median_str = format_time(median_ns)
            ops_str = format_ops(ops)
            
            print(f"\033[1;32m║    {name:<41} │ {min_str:>8} │ {mean_str:>8} │ {median_str:>8} │ {status} {ops_str:>12}/s ║\033[0m")
    
    print("\033[1;32m╚══════════════════════════════════════════════════════════════════════════════════════════════════╝\033[0m")
    
    # Print legend
    print("")
    print("\033[1;33m  Legend: 🟢 Excellent (>1M ops/s)  🟡 Good (>100K ops/s)  🔴 Review (<100K ops/s)\033[0m")
    
except Exception as e:
    print(f"Error parsing results: {e}", file=sys.stderr)
EOF
}

print_comparison_table() {
    local json_file="$1"
    local baseline_dir=".benchmarks"
    
    if [ ! -d "$baseline_dir" ]; then
        echo -e "${YELLOW}  No baseline found. Run with --save first.${NC}"
        return
    fi
    
    # Find latest baseline
    local baseline_file=$(ls -t "$baseline_dir"/*/*.json 2>/dev/null | head -1)
    
    if [ -z "$baseline_file" ] || [ ! -f "$baseline_file" ]; then
        echo -e "${YELLOW}  No baseline file found.${NC}"
        return
    fi
    
    echo ""
    echo -e "${BOLD}${YELLOW}╔══════════════════════════════════════════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${YELLOW}║                                     📈 COMPARISON WITH BASELINE                                          ║${NC}"
    echo -e "${BOLD}${YELLOW}╠══════════════════════════════════════════════════════════════════════════════════════════════════════════╣${NC}"
    echo -e "${BOLD}${YELLOW}║  Test Name                                    │  Current  │  Baseline │   Diff   │  Status              ║${NC}"
    echo -e "${BOLD}${YELLOW}╠═══════════════════════════════════════════════╪═══════════╪═══════════╪══════════╪══════════════════════╣${NC}"
    
    python3 << EOF
import json
import sys

try:
    with open("$json_file", "r") as f:
        current = json.load(f)
    
    with open("$baseline_file", "r") as f:
        baseline = json.load(f)
    
    current_benchmarks = {b["name"]: b for b in current.get("benchmarks", [])}
    baseline_benchmarks = {b["name"]: b for b in baseline.get("benchmarks", [])}
    
    def format_time(ns):
        if ns < 1000:
            return f"{ns:.1f} ns"
        elif ns < 1000000:
            return f"{ns/1000:.2f} µs"
        else:
            return f"{ns/1000000:.2f} ms"
    
    for name, curr in sorted(current_benchmarks.items()):
        if name not in baseline_benchmarks:
            continue
        
        base = baseline_benchmarks[name]
        
        curr_mean = curr["stats"]["mean"] * 1e9
        base_mean = base["stats"]["mean"] * 1e9
        
        diff_pct = ((curr_mean - base_mean) / base_mean) * 100
        
        if diff_pct < -5:
            status = "🚀 Faster"
            color = "\033[1;32m"
        elif diff_pct > 10:
            status = "⚠️  Slower"
            color = "\033[1;31m"
        elif diff_pct > 5:
            status = "📉 Regressed"
            color = "\033[1;33m"
        else:
            status = "✅ Same"
            color = "\033[1;32m"
        
        short_name = name.replace("test_", "")[:40]
        curr_str = format_time(curr_mean)
        base_str = format_time(base_mean)
        diff_str = f"{diff_pct:+.1f}%"
        
        print(f"\033[1;33m║  {short_name:<43} │ {curr_str:>9} │ {base_str:>9} │ {diff_str:>8} │ {color}{status:<15}\033[1;33m ║\033[0m")
    
    print("\033[1;33m╚══════════════════════════════════════════════════════════════════════════════════════════════════════════╝\033[0m")
    
except Exception as e:
    print(f"Error comparing results: {e}", file=sys.stderr)
EOF
}

print_footer() {
    echo ""
    echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ Benchmarks complete!${NC}"
    echo ""
}

# Check if pytest-benchmark is installed
if ! python3 -c "import pytest_benchmark" 2>/dev/null; then
    echo -e "${YELLOW}Installing pytest-benchmark...${NC}"
    pip install pytest-benchmark
fi

# Parse arguments
BENCH_TARGET="benchmarks/"
SAVE_MODE=false
COMPARE_MODE=false
JSON_MODE=false
JSON_FILE="/tmp/obskit_benchmark_results.json"

for arg in "$@"; do
    case $arg in
        --save)
            SAVE_MODE=true
            ;;
        --compare)
            COMPARE_MODE=true
            ;;
        --json)
            JSON_MODE=true
            ;;
        metrics|circuit_breaker|context|logging)
            BENCH_TARGET="benchmarks/bench_${arg}.py"
            ;;
    esac
done

# Print header
print_header

print_section "Configuration"
echo -e "  ${DIM}Target:${NC} $BENCH_TARGET"
echo -e "  ${DIM}Save baseline:${NC} $SAVE_MODE"
echo -e "  ${DIM}Compare mode:${NC} $COMPARE_MODE"

# Build command
BENCH_CMD="pytest $BENCH_TARGET -p no:xdist -o addopts='' --benchmark-only"
BENCH_CMD="$BENCH_CMD --benchmark-columns=min,max,mean,stddev,median,ops"
BENCH_CMD="$BENCH_CMD --benchmark-json=$JSON_FILE"
BENCH_CMD="$BENCH_CMD -q"  # Quiet mode for cleaner output

if $SAVE_MODE; then
    BENCH_CMD="$BENCH_CMD --benchmark-autosave"
fi

print_section "Running Benchmarks"
echo -e "  ${DIM}Command:${NC} pytest $BENCH_TARGET --benchmark-only"
echo ""

# Run benchmarks (capture output but still show progress)
eval $BENCH_CMD 2>&1 | grep -E "^(benchmarks/|PASSED|FAILED|ERROR|=)" || true

# Print summary table
print_summary_table "$JSON_FILE"

# Print comparison if requested
if $COMPARE_MODE; then
    print_comparison_table "$JSON_FILE"
fi

# Print JSON path if requested
if $JSON_MODE; then
    echo ""
    echo -e "${BLUE}📄 JSON results saved to: $JSON_FILE${NC}"
fi

print_footer
