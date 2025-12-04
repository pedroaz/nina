import { connectDatabase } from "../database/database";
import { User, UserModel } from "../entities/user";
import { DatabaseError, ValidationError } from "../errors";

export async function getUserById(userId: string): Promise<User | null> {
    if (!userId) {
        throw new ValidationError('User ID is required');
    }

    try {
        await connectDatabase();
        const user = await UserModel.findById(userId).exec();
        return user;
    } catch (error) {
        throw new DatabaseError(`Failed to fetch user by ID: ${userId}`, error);
    }
}

export async function getUserByEmail(email: string): Promise<User | null> {
    if (!email) {
        throw new ValidationError('Email is required');
    }

    try {
        await connectDatabase();
        const user = await UserModel.findOne({ email }).exec();
        return user;
    } catch (error) {
        throw new DatabaseError(`Failed to fetch user by email: ${email}`, error);
    }
}