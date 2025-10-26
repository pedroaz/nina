import { Lesson } from "shared";
import { Button } from "@/components/ui/button"


export default function Home() {
  const lesson: Lesson = {
    id: "1",
    title: "Introduction to React"
  };

  return (
    <>
      <h1>Welcome, Pedro</h1>
      <div>
        <h2>Current Lesson</h2>
        <p><strong>ID:</strong> {lesson.id}</p>
        <p><strong>Title:</strong> {lesson.title}</p>
        <Button>Click me</Button>

      </div>
    </>
  );
}
