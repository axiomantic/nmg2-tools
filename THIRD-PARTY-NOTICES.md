# Third-party notices

This repository is licensed under the MIT licence; see `LICENSE`. It draws on
third-party sources whose licences carry a notice requirement for redistributed
source. Those notices are reproduced below, verbatim from the upstream.

The clean-room rule in `AGENTS.md` and `README.md` governs what may be taken
from any upstream at all.

## sirlensalot/g2fx

Upstream: <https://github.com/sirlensalot/g2fx>. Licence: BSD-3-Clause.

`nmg2_tools/wire_compose.py` draws on this project for USB wire-protocol
material: message framing, field widths, and code point values. Its
`entry_name_field` follows the length-with-terminator behaviour of the g2fx
`StringField(16, lengthWithTerm)` used for `Protocol.EntryName`, and its
docstring describes that behaviour. The notice below is reproduced because
BSD-3-Clause requires it of redistributed source, and it applies whether or not
any individual passage crosses from fact into expression.

```
BSD 3-Clause License

Copyright (c) 2024, Stuart Popejoy

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
