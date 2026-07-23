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


if __name__ == "__main__":
    unittest.main()
