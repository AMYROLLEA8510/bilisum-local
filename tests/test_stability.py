import json
import time
import unittest
from unittest import mock

from host.bilisum_host import core, native


class StabilityTests(unittest.TestCase):
    def tearDown(self):
        with core.JOBS_LOCK:
            core.JOBS.clear()
        with core.BATCH_LEASE_LOCK:
            core.BATCH_LEASES.clear()
        core.set_note_parallelism(1)

    def test_dynamic_context_selection(self):
        short = [{"role": "user", "content": "x" * 2000}]
        medium = [{"role": "user", "content": "x" * 9000}]
        long = [{"role": "user", "content": "x" * 22000}]
        self.assertEqual(core._choose_num_ctx(short), 8192)
        self.assertEqual(core._choose_num_ctx(medium), 16384)
        self.assertEqual(core._choose_num_ctx(long), 32768)

    def test_auto_parallelism_is_conservative(self):
        with mock.patch.object(core, "physical_memory_gb", return_value=16), \
             mock.patch.object(core, "gpu_memory_gb", return_value=0), \
             mock.patch.object(core.platform, "system", return_value="Windows"):
            self.assertEqual(core.recommended_note_parallelism(), 1)
        with mock.patch.object(core, "physical_memory_gb", return_value=32), \
             mock.patch.object(core, "gpu_memory_gb", return_value=16), \
             mock.patch.object(core.platform, "system", return_value="Windows"):
            self.assertEqual(core.recommended_note_parallelism(), 2)

    def test_batch_lease_blocks_until_released(self):
        lease = core.batch_lease_begin(ttl_sec=60)
        self.assertTrue(core.batch_lease_active())
        core.batch_lease_heartbeat(lease["lease_id"], ttl_sec=60)
        core.batch_lease_end(lease["lease_id"])
        self.assertFalse(core.batch_lease_active())

    def test_large_asr_result_is_paged(self):
        job_id = "paged-test"
        segments = [{"from": i, "to": i + 1, "content": "中" * 120} for i in range(7000)]
        with core.JOBS_LOCK:
            core.JOBS[job_id] = {
                "job_id": job_id,
                "kind": "asr",
                "status": "done",
                "stage": "done",
                "progress": 100,
                "created_at": time.time(),
                "updated_at": time.time(),
                "result": {"segments": segments, "model": "small"},
            }
        public = core.public_job(job_id)
        self.assertTrue(public["result"]["paged"])
        self.assertEqual(public["result"]["segment_count"], len(segments))
        page = core.job_result_page(job_id, 0, 400)
        self.assertEqual(len(page["segments"]), 400)
        self.assertFalse(page["done"])

    def test_streaming_ollama_progress(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def __iter__(self):
                payloads = [
                    {"message": {"content": "你好"}, "done": False},
                    {"message": {"content": "，世界"}, "done": False},
                    {"message": {"content": ""}, "done": True, "prompt_eval_count": 12, "eval_count": 4},
                ]
                for item in payloads:
                    yield (json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8")

        job_id = "stream-test"
        with core.JOBS_LOCK:
            core.JOBS[job_id] = {
                "job_id": job_id, "kind": "notes", "status": "running", "stage": "generating",
                "created_at": time.time(), "updated_at": time.time(), "payload": {},
            }
        with mock.patch.object(core.urllib.request, "urlopen", return_value=FakeResponse()):
            content, meta = core._ollama_chat_stream({"model": "x", "messages": [], "stream": True}, job_id, 5)
        self.assertEqual(content, "你好，世界")
        self.assertEqual(meta["eval_count"], 4)
        self.assertGreater(meta["generated_chars"], 0)

    def test_update_is_blocked_by_batch_lease(self):
        lease = core.batch_lease_begin(ttl_sec=60)
        try:
            with self.assertRaises(RuntimeError):
                native.dispatch("updates.stage", {})
        finally:
            core.batch_lease_end(lease["lease_id"])


if __name__ == "__main__":
    unittest.main()
