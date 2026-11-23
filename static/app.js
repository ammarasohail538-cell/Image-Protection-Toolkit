// ========================================================
// Antigravity AI Image Protection Toolkit Client JavaScript
// ========================================================

// Modal Management System for User Pop-Ups
function showAppModal({ title, message, type = "error", icon = null, buttonText = "Acknowledge" }) {
    const modal = document.getElementById("app-modal");
    if (!modal) {
        alert(message);
        return;
    }

    const titleElem = document.getElementById("modal-title");
    const bodyElem = document.getElementById("modal-body");
    const iconContainer = document.getElementById("modal-icon-container");
    const btnElem = document.getElementById("modal-confirm-btn");

    if (titleElem) titleElem.textContent = title;
    if (bodyElem) bodyElem.innerHTML = typeof message === "string" ? message : "";
    if (btnElem) btnElem.textContent = buttonText;

    // Set icon & styling classes based on error/warning/success
    if (iconContainer) {
        iconContainer.className = "modal-icon-wrapper modal-" + type;
        if (type === "error") {
            iconContainer.innerHTML = `
                <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="15" y1="9" x2="9" y2="15"></line>
                    <line x1="9" y1="9" x2="15" y2="15"></line>
                </svg>
            `;
        } else if (type === "warning") {
            iconContainer.innerHTML = `
                <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                    <line x1="12" y1="9" x2="12" y2="13"></line>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
            `;
        } else if (type === "success") {
            iconContainer.innerHTML = `
                <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                    <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
            `;
        }
    }

    modal.style.display = "flex";
    modal.classList.add("modal-open");
}

window.closeAppModal = function() {
    const modal = document.getElementById("app-modal");
    if (modal) {
        modal.style.display = "none";
        modal.classList.remove("modal-open");
    }
};

// Close modal when pressing Escape or clicking backdrop
window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAppModal();
});

document.addEventListener("DOMContentLoaded", () => {
    const modal = document.getElementById("app-modal");
    if (modal) {
        modal.addEventListener("click", (e) => {
            if (e.target === modal) closeAppModal();
        });
    }
});

// Client-side file type verification
function validateSelectedFiles(files, toolName) {
    if (!files || files.length === 0) return { valid: false, message: "Please select at least one file." };

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const name = file.name.toLowerCase();

        if (toolName === "decrypt") {
            if (!name.endsWith(".enc") && !name.endsWith(".zip")) {
                return {
                    valid: false,
                    title: "Wrong File Selected for Decryption",
                    message: `<strong>"${escapeHtml(file.name)}"</strong> is not an encrypted file or encrypted archive.<br><br>The Decryption tool accepts individual <code>.enc</code> encrypted files OR your downloaded encrypted batch <code>.zip</code> archive. Please select a valid <code>.enc</code> file or your batch <code>.zip</code> folder.`,
                    type: "warning"
                };
            }
        } else if (toolName === "encrypt") {
            if (name.endsWith(".enc")) {
                return {
                    valid: false,
                    title: "File Already Encrypted",
                    message: `<strong>"${escapeHtml(file.name)}"</strong> is already encrypted. You cannot re-encrypt a file that has already been locked. Please upload a standard image (JPG, PNG, WEBP, BMP).`,
                    type: "warning"
                };
            }
        }
    }
    return { valid: true };
}

// Sends a form with fetch() so the page can show a result message.
// On success the server returns a file; on failure it returns JSON with a message.
function setupForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return;  // this page doesn't have that form
    const toolName = form.getAttribute("data-tool") || "";
    const submitBtn = form.querySelector('button[type="submit"]');
    const spinner = submitBtn ? submitBtn.querySelector(".btn-spinner") : null;
    const btnText = submitBtn ? submitBtn.querySelector(".btn-text") : null;
    const originalText = btnText ? btnText.textContent : "Submit";
    const fileInput = form.querySelector('input[type="file"]');

    form.addEventListener("submit", async (event) => {
        // fetch() sends the form in the background (AJAX), so the page stays open and can show a message
        event.preventDefault();  // stop the normal page reload

        // Client-side validation: Check files
        if (fileInput && fileInput.files) {
            const check = validateSelectedFiles(fileInput.files, toolName);
            if (!check.valid) {
                showAppModal({
                    title: check.title || "File Selection Warning",
                    message: check.message,
                    type: check.type || "warning"
                });
                return;
            }
        }

        // Client-side validation: Check password requirement
        const passwordInput = form.querySelector('input[type="password"]');
        if (passwordInput && !passwordInput.value.trim()) {
            showAppModal({
                title: "Password Required",
                message: "Please enter a password before proceeding with encryption or decryption.",
                type: "warning"
            });
            passwordInput.focus();
            return;
        }

        if (submitBtn) submitBtn.disabled = true;
        if (spinner) spinner.style.display = "inline-block";
        if (btnText) btnText.textContent = "Processing...";

        try {
            // FormData packs the chosen file and the password exactly as a normal form would
            const formData = new FormData(form);

            // await pauses this function until the server replies, without freezing the page
            const response = await fetch(form.action || window.location.pathname, {
                method: "POST",
                body: formData
            });

            if (response.ok) {
                // success: save the returned file through a temporary download link
                const disposition = response.headers.get("Content-Disposition") || "";
                const match = disposition.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
                const filename = match ? decodeURIComponent(match[1]) : "protected_output";

                // Read custom performance and change metrics returned from server
                const summaryMsg = response.headers.get("X-Summary-Message") || "Operation completed successfully.";
                const highlightVal = response.headers.get("X-Highlight-Val") || "100% COMPLETE";
                const origFormatted = response.headers.get("X-Original-Formatted");
                const outFormatted = response.headers.get("X-Output-Formatted");
                const savingsPct = parseFloat(response.headers.get("X-Savings-Percent") || "0");

                const blob = await response.blob();
                const link = document.createElement("a");
                link.href = URL.createObjectURL(blob);
                link.download = filename;
                document.body.appendChild(link);
                link.click();
                link.remove();

                // 1. Update On-Page Result Banner
                const banner = document.getElementById("operation-result-banner");
                if (banner) {
                    banner.style.display = "block";
                    const badge = document.getElementById("banner-highlight-badge");
                    const title = document.getElementById("banner-status-title");
                    const fnameElem = document.getElementById("banner-downloaded-filename");
                    const msgElem = document.getElementById("banner-detail-message");
                    const compRow = document.getElementById("banner-comparison-row");
                    const origSizeElem = document.getElementById("banner-orig-size");
                    const newSizeElem = document.getElementById("banner-new-size");
                    const savingsPill = document.getElementById("banner-savings-pill");
                    const savedPctElem = document.getElementById("banner-saved-pct");

                    if (badge) badge.textContent = highlightVal;
                    if (title) title.textContent = "Processing Complete";
                    if (fnameElem) fnameElem.textContent = "Downloaded: " + filename;
                    if (msgElem) msgElem.textContent = summaryMsg;

                    if (origFormatted && outFormatted && compRow) {
                        compRow.style.display = "flex";
                        if (origSizeElem) origSizeElem.textContent = origFormatted;
                        if (newSizeElem) newSizeElem.textContent = outFormatted;
                        if (savingsPct > 0 && savingsPill && savedPctElem) {
                            savingsPill.style.display = "inline-flex";
                            savedPctElem.textContent = savingsPct + "% Saved";
                        } else if (savingsPill) {
                            savingsPill.style.display = "none";
                        }
                    } else if (compRow) {
                        compRow.style.display = "none";
                    }

                    // Smoothly scroll banner into view
                    banner.scrollIntoView({ behavior: "smooth", block: "nearest" });
                }

                // 2. Trigger Success Pop-up Modal with Percentage and Changes Shown
                const isZip = filename.endsWith(".zip");
                let statsHtml = "";
                if (origFormatted && outFormatted) {
                    statsHtml = `
                        <div class="modal-stats-card">
                            <div class="modal-stat-item">
                                <span class="m-stat-lbl">Original Size:</span>
                                <strong>${origFormatted}</strong>
                            </div>
                            <span class="m-stat-arrow">➔</span>
                            <div class="modal-stat-item">
                                <span class="m-stat-lbl">Processed Size:</span>
                                <strong style="color: #10B981;">${outFormatted}</strong>
                            </div>
                        </div>
                    `;
                }

                showAppModal({
                    title: highlightVal,
                    message: `
                        <p style="font-weight: 600; color: #F9FAFB; margin-bottom: 0.5rem; font-size: 1.05rem;">${escapeHtml(summaryMsg)}</p>
                        ${statsHtml}
                        <p style="color: #94A3B8; font-size: 0.875rem; margin-top: 0.75rem;">File ready and downloaded: <strong style="color: #60A5FA;">${escapeHtml(filename)}</strong></p>
                        ${isZip ? '<p style="font-size: 0.8rem; color: #94A3B8; margin-top: 0.35rem;">All batch files have been packaged inside this ZIP archive.</p>' : ''}
                    `,
                    type: "success",
                    buttonText: "Done"
                });
            } else {
                const result = await response.json().catch(() => ({
                    message: "The server encountered an error processing your request."
                }));

                // Check specifically for wrong password vs wrong file
                if (result.error_type === "wrong_password") {
                    showAppModal({
                        title: "Decryption Failed: Incorrect Password",
                        message: `
                            <strong>Authentication Verification Failed!</strong><br><br>
                            The password entered does not match this file, or the file has been tampered with or corrupted.<br><br>
                            <em>Cryptographic SHA-256 integrity check rejected the key.</em> Please verify your password and try again.
                        `,
                        type: "error",
                        buttonText: "Try Again"
                    });
                } else if (result.error_type === "wrong_file_type") {
                    showAppModal({
                        title: "Invalid File Format",
                        message: `<strong>File Rejected:</strong><br><br>${escapeHtml(result.message)}`,
                        type: "warning",
                        buttonText: "Select Another File"
                    });
                } else {
                    showAppModal({
                        title: "Operation Error",
                        message: escapeHtml(result.message || "Failed to process image."),
                        type: "error",
                        buttonText: "Close"
                    });
                }
            }
        } catch (error) {
            showAppModal({
                title: "Network Connection Error",
                message: "Could not communicate with the local server. Ensure the Flask server is running.",
                type: "error"
            });
        } finally {
            if (submitBtn) submitBtn.disabled = false;
            if (spinner) spinner.style.display = "none";
            if (btnText) btnText.textContent = originalText;
        }
    });
}

setupForm("tool-form");
setupForm("encrypt-form");
setupForm("decrypt-form");

// The multi-algorithm hash checker returns JSON
function setupHashForm() {
    const form = document.getElementById("hash-form");
    if (!form) return;
    const outputCard = document.getElementById("hash-result-card");
    const outputContainer = document.getElementById("hash-output");
    const submitBtn = document.getElementById("hash-submit-btn");

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (outputCard) outputCard.style.display = "block";
        if (outputContainer) outputContainer.innerHTML = '<p class="status-box loading">Computing cryptographic digests across streaming buffers...</p>';
        if (submitBtn) submitBtn.disabled = true;

        try {
            const response = await fetch(form.action, { method: "POST", body: new FormData(form) });
            const result = await response.json();

            if (!response.ok) {
                showAppModal({
                    title: "Hash Calculation Error",
                    message: escapeHtml(result.message || "Failed to compute file digests."),
                    type: "error"
                });
                if (outputCard) outputCard.style.display = "none";
                return;
            }

            let html = `
                <div class="hash-row">
                    <div class="hash-row-title">Primary File: <strong>${escapeHtml(result.name1)}</strong></div>
                    <div class="hash-digest-block">
                        <div class="digest-item"><span class="algo-pill">SHA-256</span> <code>${result.hashes1.sha256}</code></div>
                        <div class="digest-item"><span class="algo-pill">MD5</span> <code>${result.hashes1.md5}</code></div>
                        <div class="digest-item"><span class="algo-pill">SHA-1</span> <code>${result.hashes1.sha1}</code></div>
                    </div>
                </div>
            `;

            if (result.name2) {
                html += `
                    <div class="hash-row">
                        <div class="hash-row-title">Comparison File: <strong>${escapeHtml(result.name2)}</strong></div>
                        <div class="hash-digest-block">
                            <div class="digest-item"><span class="algo-pill">SHA-256</span> <code>${result.hashes2.sha256}</code></div>
                            <div class="digest-item"><span class="algo-pill">MD5</span> <code>${result.hashes2.md5}</code></div>
                            <div class="digest-item"><span class="algo-pill">SHA-1</span> <code>${result.hashes2.sha1}</code></div>
                        </div>
                    </div>
                `;

                if (result.match) {
                    html += `
                        <div class="hash-match-box match">
                            <span>✓ AUTHENTIC MATCH: Both files are 100% bit-for-bit identical. No tampering detected.</span>
                        </div>
                    `;
                } else {
                    html += `
                        <div class="hash-match-box mismatch">
                            <span>⚠ CRYPTOGRAPHIC MISMATCH: Files have different binary fingerprints. Data was altered or tampered with.</span>
                        </div>
                    `;
                }
            }

            if (outputContainer) outputContainer.innerHTML = html;
        } catch (error) {
            showAppModal({
                title: "Hashing Error",
                message: "Could not reach the hashing service.",
                type: "error"
            });
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    });
}

setupHashForm();

// Shows the AI password-strength result under a password box while the user types.
function attachStrengthMeter(inputId, outputId) {
    const input = document.getElementById(inputId);
    const output = document.getElementById(outputId);
    if (!input || !output) return;
    let timer;

    input.addEventListener("input", () => {
        clearTimeout(timer);  // wait until the user pauses typing (300 ms) before asking the server
        timer = setTimeout(async () => {
            const password = input.value;
            if (!password) {
                output.style.display = "none";
                output.innerHTML = "";
                return;
            }

            const data = new FormData();
            data.append("password", password);

            try {
                const response = await fetch("/password-strength", { method: "POST", body: data });
                if (!response.ok) return;
                const result = await response.json();

                output.style.display = "block";

                // Check if this is the dedicated AI page with complex metrics
                const scoreElem = document.getElementById("strength-score");
                const labelElem = document.getElementById("strength-label");
                const barElem = document.getElementById("strength-bar");
                const tipsElem = document.getElementById("strength-tips");
                const entropyElem = document.getElementById("entropy-score");
                const crackTimeElem = document.getElementById("crack-time-display");

                if (scoreElem && labelElem && barElem) {
                    scoreElem.textContent = result.score;
                    labelElem.textContent = result.label;
                    labelElem.className = "strength-badge " + result.label.toLowerCase();

                    barElem.style.width = Math.max(result.score, 5) + "%";
                    barElem.className = "progress-bar-fill " + result.label.toLowerCase();

                    if (entropyElem) entropyElem.textContent = result.entropy;
                    if (crackTimeElem) crackTimeElem.textContent = result.crack_time;

                    // Update composition badges
                    if (result.composition) {
                        const comp = result.composition;
                        const updateBadge = (id, active) => {
                            const el = document.getElementById(id);
                            if (el) el.classList.toggle("active", Boolean(active));
                        };
                        updateBadge("badge-upper", comp.has_upper);
                        updateBadge("badge-lower", comp.has_lower);
                        updateBadge("badge-digit", comp.has_digit);
                        updateBadge("badge-symbol", comp.has_symbol);
                    }

                    if (tipsElem) {
                        tipsElem.innerHTML = result.tips.map(tip => `
                            <div class="tip-item">
                                <span>•</span> <span>${escapeHtml(tip)}</span>
                            </div>
                        `).join("");
                    }
                } else {
                    // Inline meter for encrypt form
                    const badgeClass = result.label.toLowerCase();
                    output.innerHTML = `
                        <div style="margin-top: 0.5rem; display: flex; align-items: center; gap: 0.75rem; flex-wrap: wrap;">
                            <span class="strength-badge ${badgeClass}">${result.label}</span>
                            <span style="font-size: 0.825rem; color: var(--text-secondary);">AI Score: <strong>${result.score}/100</strong></span>
                            <span style="font-size: 0.825rem; color: var(--text-muted);">Entropy: <strong>${result.entropy} bits</strong></span>
                        </div>
                        ${result.tips.length ? `<div style="font-size: 0.8rem; color: #FCD34D; margin-top: 0.35rem;">${escapeHtml(result.tips[0])}</div>` : ''}
                    `;
                }
            } catch (error) {
                // Silently ignore typing error
            }
        }, 300);
    });
}

attachStrengthMeter("encrypt-password", "encrypt-strength");
attachStrengthMeter("checker-password", "checker-result");

// Drag and drop file selector enhancement (with multi-file support and client pop-up validation)
function initDropzones() {
    document.querySelectorAll(".dropzone").forEach(dropzone => {
        const fileInput = dropzone.querySelector('input[type="file"]');
        if (!fileInput) return;

        const form = dropzone.closest("form");
        const toolName = form ? form.getAttribute("data-tool") || "" : "";
        const previewList = dropzone.querySelector(".file-preview-list");
        const dropzoneTitle = dropzone.querySelector(".dropzone-title");
        const previewText = dropzone.querySelector(".file-preview-text");

        function updateFileList(files) {
            if (!files || files.length === 0) return;

            // Trigger client pop-up validation immediately upon selection
            const check = validateSelectedFiles(files, toolName);
            if (!check.valid) {
                fileInput.value = "";
                if (previewList) previewList.style.display = "none";
                if (previewText) previewText.style.display = "none";
                showAppModal({
                    title: check.title || "File Format Error",
                    message: check.message,
                    type: check.type || "warning"
                });
                return;
            }

            if (previewList) {
                previewList.innerHTML = "";
                let totalBytes = 0;

                Array.from(files).forEach((file, idx) => {
                    totalBytes += file.size;
                    const pill = document.createElement("div");
                    pill.className = "file-pill";
                    pill.innerHTML = `
                        <span class="file-pill-name">${escapeHtml(file.name)}</span>
                        <span class="file-pill-size">(${formatBytes(file.size)})</span>
                    `;
                    previewList.appendChild(pill);
                });

                previewList.style.display = "flex";
                if (dropzoneTitle) {
                    dropzoneTitle.textContent = files.length === 1 
                        ? "1 File Ready" 
                        : `${files.length} Files Selected (Total: ${formatBytes(totalBytes)})`;
                }
            }

            if (previewText) {
                const f = files[0];
                previewText.textContent = `${f.name} (${formatBytes(f.size)})`;
                previewText.style.display = "block";
            }
        }

        fileInput.addEventListener("change", () => {
            if (fileInput.files) updateFileList(fileInput.files);
        });

        ["dragenter", "dragover"].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.add("dragover");
            }, false);
        });

        ["dragleave", "drop"].forEach(eventName => {
            dropzone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropzone.classList.remove("dragover");
            }, false);
        });

        dropzone.addEventListener("drop", (e) => {
            if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                fileInput.files = e.dataTransfer.files;
                updateFileList(fileInput.files);
            }
        });
    });
}

document.addEventListener("DOMContentLoaded", initDropzones);

// Helper function to format file sizes
function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

// Password Generator helper
window.generateAndSetPassword = async function(inputId) {
    try {
        const response = await fetch("/password-generate");
        const data = await response.json();
        if (data.ok && data.password) {
            const input = document.getElementById(inputId);
            if (input) {
                input.value = data.password;
                input.dispatchEvent(new Event("input"));
            }
        }
    } catch (err) {
        // Fallback generator
        const input = document.getElementById(inputId);
        if (input) {
            const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*-_=+";
            let pw = "";
            for (let i = 0; i < 16; i++) pw += chars.charAt(Math.floor(Math.random() * chars.length));
            input.value = pw;
            input.dispatchEvent(new Event("input"));
        }
    }
};

// Preset dimensions helper for Resize tool
window.applyResolutionPreset = function(select) {
    const val = select.value;
    const widthInput = document.getElementById("width-input");
    const heightInput = document.getElementById("height-input");
    if (!widthInput || !heightInput) return;

    if (val === "custom") {
        heightInput.value = "";
    } else {
        const parts = val.split("x");
        widthInput.value = parts[0];
        heightInput.value = parts[1];
    }
};

// EXIF Metadata Inspector handler
window.inspectUploadedMetadata = async function() {
    const fileInput = document.getElementById("file-input");
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        showAppModal({
            title: "File Required",
            message: "Please select an image file first to inspect its EXIF metadata tags.",
            type: "warning"
        });
        return;
    }

    const btn = document.getElementById("btn-inspect-exif");
    const origText = btn ? btn.textContent : "";
    if (btn) btn.textContent = "Analyzing EXIF Data...";

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);

    try {
        const response = await fetch("/tool/metadata/inspect", {
            method: "POST",
            body: formData
        });
        const result = await response.json();

        if (!response.ok || !result.ok) {
            showAppModal({
                title: "Metadata Analysis Notice",
                message: escapeHtml(result.message || "Could not read EXIF data."),
                type: "warning"
            });
            return;
        }

        const previewCard = document.getElementById("metadata-preview-card");
        const contentContainer = document.getElementById("metadata-content");
        const statusBadge = document.getElementById("metadata-status-badge");

        if (previewCard && contentContainer) {
            previewCard.style.display = "block";
            const info = result.info;

            if (statusBadge) {
                if (info["Has EXIF"]) {
                    statusBadge.className = "badge badge-danger";
                    statusBadge.textContent = "Sensitive EXIF Detected";
                } else {
                    statusBadge.className = "badge badge-success";
                    statusBadge.textContent = "Clean / No EXIF Tags";
                }
            }

            let html = `
                <div class="meta-item"><span class="meta-label">Format:</span> <strong>${info.Format}</strong></div>
                <div class="meta-item"><span class="meta-label">Color Space:</span> <strong>${info.Mode}</strong></div>
                <div class="meta-item"><span class="meta-label">Dimensions:</span> <strong>${info.Dimensions}</strong></div>
            `;

            if (info.Details && Object.keys(info.Details).length > 0) {
                for (const [key, val] of Object.entries(info.Details)) {
                    html += `<div class="meta-item meta-item-detail"><span class="meta-label">${escapeHtml(key)}:</span> <code>${escapeHtml(String(val))}</code></div>`;
                }
            } else {
                html += `<div class="meta-empty">No device, GPS, or camera hardware tags detected in this image.</div>`;
            }

            contentContainer.innerHTML = html;
        }
    } catch (err) {
        showAppModal({
            title: "Analysis Failed",
            message: "Failed to connect to the metadata extraction service.",
            type: "error"
        });
    } finally {
        if (btn) btn.textContent = origText;
    }
};

// Helper function to toggle password visibility
window.togglePasswordVisibility = function(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    if (input.type === "password") {
        input.type = "text";
        btn.textContent = "🙈";
    } else {
        input.type = "password";
        btn.textContent = "👁️";
    }
};

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
