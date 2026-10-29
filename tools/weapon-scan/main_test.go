package main

import (
	"github.com/markus-wa/demoinfocs-golang/v5/pkg/demoinfocs/common"
	"testing"
)

func TestEquipmentRule(t *testing.T) {
	k, g := common.EqKnife, common.EqGlock
	tests := []struct {
		name        string
		inventories [][]common.EquipmentType
		world       []common.EquipmentType
		want        string
	}{
		{"knives without kills", [][]common.EquipmentType{{k}, {k}}, []common.EquipmentType{k, k}, "knife"},
		{"survivor after falling", [][]common.EquipmentType{{k}}, []common.EquipmentType{k}, "knife"},
		{"ground pistol", [][]common.EquipmentType{{k}, {k}}, []common.EquipmentType{k, g}, "not_knife"},
		{"holstered pistol", [][]common.EquipmentType{{k, g}, {k}}, []common.EquipmentType{k, g}, "not_knife"},
		{"grenade", [][]common.EquipmentType{{k, common.EqFlash}, {k}}, []common.EquipmentType{k}, "not_knife"},
		{"empty inventory", [][]common.EquipmentType{{}, {k}}, []common.EquipmentType{k}, "unknown"},
		{"unknown world entity", [][]common.EquipmentType{{k}, {k}}, []common.EquipmentType{k, common.EqUnknown}, "unknown"},
		{"unavailable world", [][]common.EquipmentType{{k}, {k}}, nil, "unknown"},
		{"no players", nil, []common.EquipmentType{k}, "unknown"},
		{"passive armor", [][]common.EquipmentType{{k, common.EqKevlar}}, []common.EquipmentType{k}, "knife"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, _ := classify(tt.inventories, tt.world)
			if got != tt.want {
				t.Fatalf("got %s, want %s", got, tt.want)
			}
		})
	}
}
