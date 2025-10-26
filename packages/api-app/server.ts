// src/server.ts

import express from "express";
import type { Request, Response } from "express";
import cors from "cors";
import type { Lesson } from "shared";

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());

app.get("/", (req: Request, res: Response) => {
    const lesson: Lesson = {
        id: "1",
        title: "Introduction to TypeScript"
    };
    res.status(200).json({
        success: true,
        message: "API is working fine.",
        data: lesson
    });
});

app.listen(PORT, () => {
    console.log(`API is working on PORT ${PORT}`);
});
