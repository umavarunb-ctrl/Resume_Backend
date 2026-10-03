import sys

file_path = r"D:\ProjectAPI\Ram_Charan\Frontend\React\Resume_Ram\src\lib\api\upload-service.ts"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

new_content = content + """
  /**
   * Upload multiple resume PDFs to the backend FastAPI batch endpoint
   * POST /api/uploads/batch
   */
  async uploadMultipleResumes(files: File[]): Promise<UploadResumeResponse[]> {
    const formData = new FormData();
    files.forEach(file => formData.append("files", file));

    const response = await apiFetch<UploadResumeResponse[]>("/uploads/batch", {
      method: "POST",
      body: formData,
    });

    return response;
  },
}
"""

# wait, the original content ends with "};", I should remove it and add my new content.
content = content.strip()
if content.endswith("};"):
    content = content[:-2]
    content += """
  /**
   * Upload multiple resume PDFs to the backend FastAPI batch endpoint
   * POST /api/uploads/batch
   */
  async uploadMultipleResumes(files: File[]): Promise<UploadResumeResponse[]> {
    const formData = new FormData();
    files.forEach(file => formData.append("files", file));

    const response = await apiFetch<UploadResumeResponse[]>("/uploads/batch", {
      method: "POST",
      body: formData,
    });

    return response;
  },
};
"""

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated upload-service.ts")


file_path2 = r"D:\ProjectAPI\Ram_Charan\Frontend\React\Resume_Ram\src\routes\_workspace.upload.tsx"
with open(file_path2, "r", encoding="utf-8") as f:
    content2 = f.read()

replacement_target = """  const handleUploadAll = async () => {
    const pending = files.filter((f) => f.status === "idle" || f.status === "error");
    if (pending.length === 0) return;

    setIsUploadingAll(true);
    let successCount = 0;

    for (const item of pending) {
      const ok = await uploadSingleFile(item);
      if (ok) successCount++;
    }

    setIsUploadingAll(false);
    if (successCount > 0) {
      queryClient.invalidateQueries({ queryKey: candidateQueryKeys.all });
    }
  };"""

replacement_code = """  const handleUploadAll = async () => {
    const pending = files.filter((f) => f.status === "idle" || f.status === "error");
    if (pending.length === 0) return;

    setIsUploadingAll(true);
    setFiles((current) =>
      current.map((f) =>
        pending.some((p) => p.id === f.id)
          ? { ...f, status: "uploading", errorMessage: undefined }
          : f
      )
    );

    try {
      const response = await uploadService.uploadMultipleResumes(pending.map(p => p.file));
      
      setFiles((current) =>
        current.map((f) => {
          const pendingItem = pending.find(p => p.id === f.id);
          if (!pendingItem) return f;
          
          const index = pending.indexOf(pendingItem);
          const res = response[index];
          
          if (res) {
             const candidateId = res["id"] || res["candidate_id"] || res["candidate"]?.id;
             const candidateName = res["candidate"]?.name || res["full_name"] || res["name"];
             
             return {
                ...f,
                status: "success",
                candidateId: candidateId ? String(candidateId) : undefined,
                candidateName: candidateName ? String(candidateName) : undefined,
             };
          }
          return f;
        })
      );
      toast.success(`${pending.length} resumes parsed & uploaded successfully!`);
      queryClient.invalidateQueries({ queryKey: candidateQueryKeys.all });
    } catch (err: any) {
      const message = err?.message || "Failed to upload resumes in batch.";
      setFiles((current) =>
        current.map((f) =>
          pending.some((p) => p.id === f.id)
            ? { ...f, status: "error", errorMessage: message }
            : f
        )
      );
      toast.error(`Batch upload failed: ${message}`);
    } finally {
      setIsUploadingAll(false);
    }
  };"""

if replacement_target in content2:
    content2 = content2.replace(replacement_target, replacement_code)
    with open(file_path2, "w", encoding="utf-8") as f:
        f.write(content2)
    print("Updated _workspace.upload.tsx")
else:
    print("Could not find handleUploadAll target in _workspace.upload.tsx")
