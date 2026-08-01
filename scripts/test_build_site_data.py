import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_site_data.py")
SPEC = importlib.util.spec_from_file_location("build_site_data", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TrainerAiContractTest(unittest.TestCase):
    def test_class_flags_are_derived_from_rom_helper(self):
        source = """
        static inline const u64 GetTrainerAIFlagsFromId(u16 trainerId)
        {
            u64 flags = 1;
            switch (GetTrainerClassFromId(trainerId))
            {
            case TRAINER_CLASS_LEADER:
            case TRAINER_CLASS_CHAMPION:
                flags |= AI_FLAG_SMART_TRAINER | AI_FLAG_PREDICTION;
                break;
            }
            return flags;
        }
        """
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.h"
            path.write_text(source, encoding="utf-8")
            result = MODULE.parse_class_auto_ai_flags(path)
        self.assertEqual(result["leader"], ["Smart Trainer", "Prediction"])
        self.assertEqual(result["champion"], ["Smart Trainer", "Prediction"])

    def test_zero_declared_flags_do_not_receive_class_flags(self):
        result = MODULE.merge_effective_ai_flags(
            [],
            "Leader",
            {"leader": ["Smart Trainer", "Prediction"]},
        )
        self.assertEqual(result, [])

    def test_class_groups_can_have_distinct_effective_profiles(self):
        source = """
        static inline const u64 GetTrainerAIFlagsFromId(u16 trainerId)
        {
            u64 flags = 1;
            enum TrainerClassID trainerClass = GetTrainerClassFromId(trainerId);
            switch (trainerClass)
            {
            case TRAINER_CLASS_LEADER:
            case TRAINER_CLASS_CHAMPION:
                flags |= AI_FLAG_SMART_TRAINER | AI_FLAG_PREDICTION;
                break;
            case TRAINER_CLASS_RIVAL:
            case TRAINER_CLASS_AQUA_ADMIN:
                flags |= AI_FLAG_FAIR_SMART_TRAINER | AI_FLAG_PREFER_HIGHEST_DAMAGE_MOVE;
                break;
            default:
                break;
            }
            return flags;
        }
        """
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.h"
            path.write_text(source, encoding="utf-8")
            result = MODULE.parse_class_auto_ai_flags(path)

        self.assertEqual(result["leader"], ["Smart Trainer", "Prediction"])
        self.assertEqual(result["champion"], ["Smart Trainer", "Prediction"])
        self.assertEqual(result["rival"], ["Fair Smart Trainer", "Prefer Highest Damage Move"])
        self.assertEqual(result["aqua admin"], ["Fair Smart Trainer", "Prefer Highest Damage Move"])

    def test_declared_and_class_flags_are_merged_without_duplicates(self):
        result = MODULE.merge_effective_ai_flags(
            ["Basic Trainer", "Prediction"],
            "Leader",
            {"leader": ["Smart Trainer", "Prediction"]},
        )
        self.assertEqual(result, ["Basic Trainer", "Prediction", "Smart Trainer"])

    def test_trainer_specific_flags_are_derived_and_merged(self):
        source = """
        static inline const u64 GetTrainerAIFlagsFromId(u16 trainerId)
        {
            u64 flags = 1;
            if (trainerId == TRAINER_HAYDEN)
                flags |= AI_FLAG_SMART_TRAINER | AI_FLAG_PREDICTION;
            switch (GetTrainerClassFromId(trainerId))
            {
            case TRAINER_CLASS_LEADER:
                flags |= AI_FLAG_SMART_TRAINER | AI_FLAG_OMNISCIENT;
                break;
            }
            return flags;
        }
        """
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.h"
            path.write_text(source, encoding="utf-8")
            trainer_flags = MODULE.parse_trainer_auto_ai_flags(path, {"TRAINER_HAYDEN": 707})
            class_flags = MODULE.parse_class_auto_ai_flags(path)

        self.assertEqual(trainer_flags["TRAINER_HAYDEN"], ["Smart Trainer", "Prediction"])
        self.assertEqual(class_flags["leader"], ["Smart Trainer", "Omniscient"])
        self.assertEqual(
            MODULE.merge_effective_ai_flags(
                ["Check Bad Move"],
                "Hayden",
                class_flags,
                "TRAINER_HAYDEN",
                trainer_flags,
            ),
            ["Check Bad Move", "Smart Trainer", "Prediction"],
        )


class TrainerRuntimeMetadataTest(unittest.TestCase):
    def test_runtime_level_rule_is_attached_to_legal_trainer(self):
        source = """
=== TRAINER_DIGLETT_MASTER ===
Name: DIGLETT
Class: Ruin Maniac
AI: Check Bad Move

Diglett
Level: 5
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trainers.party"
            path.write_text(source, encoding="utf-8")
            trainers = MODULE.parse_showdown_trainers(
                path,
                {"diglett": 50},
                {"TRAINER_DIGLETT_MASTER": 857},
                {
                    857: {
                        "zone": "Altering Cave",
                        "map": "AlteringCave",
                        "zoneOrder": 0,
                        "firstOrder": 0,
                    }
                },
                {
                    857: {
                        "levelRule": {
                            "kind": "playerLeadMinus",
                            "offset": 11,
                            "min": 1,
                        }
                    }
                },
                {},
                {},
                {},
            )

        self.assertEqual(
            trainers[0]["levelRule"],
            {"kind": "playerLeadMinus", "offset": 11, "min": 1},
        )


if __name__ == "__main__":
    unittest.main()
