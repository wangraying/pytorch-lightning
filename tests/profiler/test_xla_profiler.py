# Copyright The PyTorch Lightning team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
from multiprocessing import Event, Process
from unittest.mock import patch

import pytest

from pytorch_lightning import Trainer
from pytorch_lightning.profiler import XLAProfiler
from pytorch_lightning.utilities import _TORCH_GREATER_EQUAL_1_8, _TPU_AVAILABLE
from pytorch_lightning.utilities.exceptions import MisconfigurationException
from tests.helpers import BoringModel
from tests.helpers.runif import RunIf

if _TPU_AVAILABLE:
    import torch_xla.utils.utils as xu

    if _TORCH_GREATER_EQUAL_1_8:
        import torch_xla.debug.profiler as xp


@RunIf(tpu=True)
def test_xla_profiler_instance(tmpdir):

    model = BoringModel()
    trainer = Trainer(default_root_dir=tmpdir, fast_dev_run=True, profiler="xla", tpu_cores=8)

    assert isinstance(trainer.profiler, XLAProfiler)
    trainer.fit(model)
    assert trainer.state.finished, f"Training failed with {trainer.state}"


@pytest.mark.skipif(True, reason="XLA Profiler doesn't support Prog. capture yet")
def test_xla_profiler_prog_capture(tmpdir):

    port = xu.get_free_tcp_ports()[0]
    training_started = Event()

    def train_worker():
        model = BoringModel()
        trainer = Trainer(default_root_dir=tmpdir, max_epochs=4, profiler="xla", tpu_cores=8)

        trainer.fit(model)

    p = Process(target=train_worker, daemon=True)
    p.start()
    training_started.wait(120)

    logdir = str(tmpdir)
    xp.trace(f"localhost:{port}", logdir, duration_ms=2000, num_tracing_attempts=5, delay_ms=1000)

    p.terminate()

    assert os.isfile(os.path.join(logdir, "plugins", "profile", "*", "*.xplane.pb"))


@patch("pytorch_lightning.utilities.imports._TPU_AVAILABLE", return_value=False)
def test_xla_profiler_tpu_not_available_exception(*_):
    with pytest.raises(MisconfigurationException, match="`XLAProfiler` is only supported on TPUs"):
        _ = XLAProfiler()


@RunIf(max_torch="1.8.0")
@patch("pytorch_lightning.utilities.imports._TPU_AVAILABLE", return_value=True)
def test_xla_profiler_torch_lesser_than_1_8_exception(*_):
    with pytest.raises(MisconfigurationException, match="`XLAProfiler` is only supported with `torch-xla>=1.8`"):
        _ = XLAProfiler()
