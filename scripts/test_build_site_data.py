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


if __name__ == "__main__":
    unittest.main()
