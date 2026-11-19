package broker

import (
	"github.com/shirou/gopsutil/v4/process"
	"os"
)

func processResources() Object {
	result := Object{"rss_bytes": nil, "cpu_percent": nil, "owned_subprocess_count": 0, "scope": "broker process only; hosts and model servers are independent"}
	p, err := process.NewProcess(int32(os.Getpid()))
	if err != nil {
		return result
	}
	if memory, err := p.MemoryInfo(); err == nil {
		result["rss_bytes"] = memory.RSS
	}
	if cpu, err := p.CPUPercent(); err == nil {
		result["cpu_percent"] = cpu
		result["cpu_measurement"] = "process lifetime CPU percentage"
	}
	return result
}
