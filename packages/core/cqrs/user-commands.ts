import { connectDatabase } from "../database/database";
import { StudentLevel } from "../entities/student";
import { UserModel } from "../entities/user";

export interface CreateUserData {
    name: string;
    email: string;
    level: StudentLevel;
}

export async function createUserCommand(userData: CreateUserData) {
    await connectDatabase();
    const user = new UserModel(userData);
    await user.save();
}