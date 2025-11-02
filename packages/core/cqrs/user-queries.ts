import { connectDatabase } from "../database/database";
import { User, UserModel } from "../entities/user";

export async function getUserById(userId: string): Promise<User | null> {
    await connectDatabase();
    const user = await UserModel.findById(userId).exec();
    return user;
}

export async function getUserByEmail(email: string): Promise<User | null> {
    await connectDatabase();
    const user = await UserModel.findOne({ email }).exec();
    return user;
}