package main

import (
	"encoding/json"
	"flag"
	"fmt"
	dem "github.com/markus-wa/demoinfocs-golang/v5/pkg/demoinfocs"
	"github.com/markus-wa/demoinfocs-golang/v5/pkg/demoinfocs/common"
	"github.com/markus-wa/demoinfocs-golang/v5/pkg/demoinfocs/events"
	"os"
)

type report struct {
	Method        string `json:"method"`
	Status        string `json:"status"`
	Reason        string `json:"reason"`
	CheckedFrames int    `json:"checked_frames"`
	FirstTick     int    `json:"first_tick"`
	LastTick      int    `json:"last_tick"`
}

func allowed(t common.EquipmentType) bool {
	// Armor and a defuse kit are passive equipment, not weapons.
	return t == common.EqKnife || t == common.EqKevlar || t == common.EqHelmet || t == common.EqDefuseKit
}

// classify uses the same rule for all inventories and the global weapon map.
func classify(inventories [][]common.EquipmentType, world []common.EquipmentType) (string, string) {
	unknown := len(inventories) == 0
	check := func(weapons []common.EquipmentType) (bool, bool) {
		knife := false
		for _, w := range weapons {
			if w == common.EqUnknown {
				unknown = true
				continue
			}
			if !allowed(w) {
				return false, true
			}
			knife = knife || w == common.EqKnife
		}
		return knife, false
	}
	for _, inventory := range inventories {
		knife, other := check(inventory)
		if other {
			return "not_knife", "inventory_weapon"
		}
		if !knife {
			unknown = true
		}
	}
	knife, other := check(world)
	if other {
		return "not_knife", "world_weapon"
	}
	if !knife {
		unknown = true
	}
	if unknown {
		return "unknown", "incomplete_equipment_state"
	}
	return "knife", "only_knives_in_inventories_and_world"
}

func run() error {
	file := flag.String("demo", "", "demo path")
	start := flag.Int("start", 0, "first server tick")
	end := flag.Int("end", 0, "round decision server tick")
	flag.Parse()
	if *file == "" || *start < 0 || *end <= *start {
		return fmt.Errorf("invalid scan interval")
	}
	f, err := os.Open(*file)
	if err != nil {
		return err
	}
	defer f.Close()
	parser := dem.NewParser(f)
	defer parser.Close()
	r := report{Method: "equipment-v1", Status: "unknown", Reason: "no_complete_equipment_state"}
	started, missing, finished := false, false, false
	parser.RegisterEventHandler(func(events.FrameDone) {
		g := parser.GameState()
		tick := g.IngameTick()
		if tick > *end {
			finished = true
			return
		}
		if tick < *start || g.IsWarmupPeriod() || g.IsFreezetimePeriod() {
			return
		}
		ct, t := 0, 0
		inventories := [][]common.EquipmentType{}
		for _, p := range g.Participants().Playing() {
			if !p.IsAlive() {
				continue
			}
			if p.Team == common.TeamCounterTerrorists {
				ct++
			} else if p.Team == common.TeamTerrorists {
				t++
			}
			inventory := []common.EquipmentType{}
			for _, w := range p.Weapons() {
				if w == nil {
					inventory = append(inventory, common.EqUnknown)
				} else {
					inventory = append(inventory, w.Type)
				}
			}
			inventories = append(inventories, inventory)
		}
		world := []common.EquipmentType{}
		for _, w := range g.Weapons() {
			if w == nil || w.Entity == nil {
				world = append(world, common.EqUnknown)
			} else {
				world = append(world, w.Type)
			}
		}
		status, reason := classify(inventories, world)
		if status == "not_knife" {
			r.Status = status
			r.Reason = reason
			finished = true
			return
		}
		if len(inventories) == 0 {
			return
		}
		if !started && (ct == 0 || t == 0) {
			return
		}
		if status == "unknown" {
			missing = true
			return
		}
		if !started {
			r.FirstTick = tick
			started = true
		}
		r.LastTick = tick
		r.CheckedFrames++
	})
	more := true
	for more && !finished {
		more, err = parser.ParseNextFrame()
		if err != nil {
			return err
		}
	}
	if r.Status != "not_knife" && started && !missing && finished {
		r.Status = "knife"
		r.Reason = "only_knives_in_inventories_and_world"
	}
	return json.NewEncoder(os.Stdout).Encode(r)
}

func main() {
	defer func() {
		if p := recover(); p != nil {
			fmt.Fprintln(os.Stderr, p)
			os.Exit(1)
		}
	}()
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
