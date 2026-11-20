import Link from "next/link";
import { ProjectForm } from "@/components/project-form";
import { SectionTitle } from "@/components/ui";
export default function NewProjectPage() {
  return (
    <div className="page narrow">
      <Link href="/" className="back-link">
        ← All projects
      </Link>
      <SectionTitle
        title="Create a project"
        description="Give every article the right context, audience, and voice."
      />
      <ProjectForm />
    </div>
  );
}
